"""Small, dependency-free Nextcloud CalDAV client."""

import base64
import re
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

FALLBACK_COLOR = "#3584e4"
DAV = "DAV:"
CALDAV = "urn:ietf:params:xml:ns:caldav"
APPLE = "http://apple.com/ns/ical/"


class CalDavError(Exception):
    pass


def _unfold(raw):
    lines = raw.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    out = []
    for line in lines:
        if line.startswith((" ", "\t")) and out:
            out[-1] += line[1:]
        else:
            out.append(line)
    return out


def _unescape(value):
    return value.replace("\\n", "\n").replace("\\N", "\n").replace("\\,", ",").replace("\\;", ";").replace("\\\\", "\\")


def _components(raw):
    current = None
    for line in _unfold(raw):
        upper = line.upper()
        if upper == "BEGIN:VEVENT":
            current = {}
        elif upper == "END:VEVENT" and current is not None:
            yield current
            current = None
        elif current is not None and ":" in line:
            lhs, value = line.split(":", 1)
            bits = lhs.split(";")
            name = bits[0].upper()
            params = {}
            for bit in bits[1:]:
                if "=" in bit:
                    key, val = bit.split("=", 1)
                    params[key.upper()] = val.strip('"')
            current.setdefault(name, []).append((params, value))


def _first(event, name, default=""):
    values = event.get(name) or []
    return values[0] if values else ({}, default)


def _endpoint(item, local_tz):
    params, value = item
    if params.get("VALUE", "").upper() == "DATE" or (len(value) == 8 and "T" not in value):
        parsed = datetime.strptime(value[:8], "%Y%m%d").date()
        return datetime.combine(parsed, time.min, local_tz), True
    clean = value.rstrip("Z")
    fmt = "%Y%m%dT%H%M%S" if len(clean) >= 15 else "%Y%m%dT%H%M"
    parsed = datetime.strptime(clean[:15] if len(clean) >= 15 else clean[:13], fmt)
    if value.endswith("Z"):
        parsed = parsed.replace(tzinfo=timezone.utc)
    else:
        tzid = params.get("TZID")
        try:
            parsed = parsed.replace(tzinfo=ZoneInfo(tzid)) if tzid else parsed.replace(tzinfo=local_tz)
        except ZoneInfoNotFoundError:
            parsed = parsed.replace(tzinfo=local_tz)
    return parsed.astimezone(local_tz), False


def _safe_url(value):
    value = str(value or "").strip()
    return value if re.match(r'^https://[^\s"\'<>]+$', value) else ""


def _meeting_url(event):
    for name in ("CONFERENCE", "URL", "LOCATION", "DESCRIPTION"):
        for _, value in event.get(name) or []:
            for found in re.findall(r"https://[^\s<>\"']+", value):
                found = found.rstrip(".,);]")
                if any(host in found.lower() for host in ("meet.", "zoom.", "teams.", "webex.", "jitsi.")):
                    return _safe_url(found)
    return ""


def normalize_ics(raw, calendar, local_tz, resource_url=""):
    rows = []
    for event in _components(raw):
        if _first(event, "STATUS")[1].upper() == "CANCELLED" or not event.get("DTSTART"):
            continue
        try:
            start, all_day = _endpoint(_first(event, "DTSTART"), local_tz)
            end = _endpoint(_first(event, "DTEND"), local_tz)[0] if event.get("DTEND") else start + (timedelta(days=1) if all_day else timedelta(hours=1))
        except (ValueError, TypeError):
            continue
        if end < start or (all_day and end.date() <= start.date()):
            continue
        uid = _first(event, "UID")[1]
        title = _unescape(_first(event, "SUMMARY", "(no title)")[1]).strip() or "(no title)"
        location = _unescape(_first(event, "LOCATION")[1]).strip()
        event_url = _safe_url(_first(event, "URL")[1])
        meeting_url = _meeting_url(event)
        last = end.date() - timedelta(days=1) if all_day or (end.time() == time.min and end.date() > start.date()) else end.date()
        cursor = start.date()
        if last < cursor:
            last = cursor
        while cursor <= last:
            rows.append({"id": uid, "calendarId": calendar["id"], "calendarName": calendar["name"],
                         "color": calendar["color"], "dateKey": cursor.isoformat(), "start": start.isoformat(),
                         "end": end.isoformat(), "allDay": all_day, "title": title, "location": location,
                         "meetingUrl": meeting_url, "eventUrl": event_url, "eventType": "", "responseStatus": "",
                         "resourceUrl": resource_url})
            cursor += timedelta(days=1)
    return rows


class CalDav:
    def __init__(self, server, username, password, timeout=30):
        self.server = str(server).rstrip("/")
        self.username = str(username)
        self.password = str(password).rstrip("\n")
        self.timeout = timeout
        if not self.server.startswith("https://"):
            raise CalDavError("Nextcloud server must use https://")
        if not self.username or not self.password:
            raise CalDavError("Nextcloud username and app password are required")
        quoted = urllib.parse.quote(self.username, safe="")
        self.home = self.server + "/remote.php/dav/calendars/" + quoted + "/"

    def _request(self, method, url, body, depth="1", extra_headers=None):
        token = base64.b64encode(f"{self.username}:{self.password}".encode()).decode()
        headers = {
            "Authorization": "Basic " + token, "Content-Type": "application/xml; charset=utf-8",
            "Depth": depth, "User-Agent": "Omarchy-Nextcloud-Calendar/1"}
        headers.update(extra_headers or {})
        data = body.encode() if isinstance(body, str) else body
        req = urllib.request.Request(url, data=data, method=method, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                return response.read()
        except urllib.error.HTTPError as error:
            if error.code == 401:
                raise CalDavError("authentication failed; create a fresh Nextcloud app password") from error
            raise CalDavError(f"CalDAV {method} failed with HTTP {error.code}") from error
        except OSError as error:
            raise CalDavError(f"cannot connect to Nextcloud: {error}") from error

    def calendars(self):
        body = '<?xml version="1.0"?><d:propfind xmlns:d="DAV:" xmlns:c="urn:ietf:params:xml:ns:caldav" xmlns:a="http://apple.com/ns/ical/"><d:prop><d:resourcetype/><d:displayname/><a:calendar-color/></d:prop></d:propfind>'
        root = ET.fromstring(self._request("PROPFIND", self.home, body))
        result = []
        for response in root.findall(f"{{{DAV}}}response"):
            resource = response.find(f".//{{{DAV}}}resourcetype")
            if resource is None or resource.find(f"{{{CALDAV}}}calendar") is None:
                continue
            href = response.findtext(f"{{{DAV}}}href", "")
            url = urllib.parse.urljoin(self.server + "/", href)
            name = response.findtext(f".//{{{DAV}}}displayname", "") or urllib.parse.unquote(href.rstrip("/").split("/")[-1])
            color = (response.findtext(f".//{{{APPLE}}}calendar-color", "") or FALLBACK_COLOR)[:7]
            if not re.match(r"^#[0-9a-fA-F]{6}$", color): color = FALLBACK_COLOR
            result.append({"id": href.rstrip("/").split("/")[-1], "name": name, "color": color, "url": url})
        return sorted(result, key=lambda item: item["name"].lower())

    def events(self, calendar, start, end, local_tz):
        begin = start.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        finish = end.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        body = f'''<?xml version="1.0"?><c:calendar-query xmlns:d="DAV:" xmlns:c="urn:ietf:params:xml:ns:caldav"><d:prop><c:calendar-data><c:expand start="{begin}" end="{finish}"/></c:calendar-data></d:prop><c:filter><c:comp-filter name="VCALENDAR"><c:comp-filter name="VEVENT"><c:time-range start="{begin}" end="{finish}"/></c:comp-filter></c:comp-filter></c:filter></c:calendar-query>'''
        root = ET.fromstring(self._request("REPORT", calendar["url"], body))
        rows = []
        for response in root.findall(f"{{{DAV}}}response"):
            data = response.find(f".//{{{CALDAV}}}calendar-data")
            if data is None:
                continue
            href = response.findtext(f"{{{DAV}}}href", "")
            resource_url = urllib.parse.urljoin(self.server + "/", href)
            rows.extend(normalize_ics(data.text or "", calendar, local_tz, resource_url))
        return rows

    def create_event(self, calendar, ical):
        """Create one new resource without overwriting an existing UID."""
        uid_match = re.search(r"(?m)^UID:([^\r\n]+)", ical)
        if not uid_match:
            raise CalDavError("generated event has no UID")
        name = urllib.parse.quote(uid_match.group(1), safe="") + ".ics"
        url = calendar["url"].rstrip("/") + "/" + name
        self._request("PUT", url, ical, depth="0", extra_headers={
            "Content-Type": "text/calendar; charset=utf-8", "If-None-Match": "*"})

    def resource(self, url):
        if not str(url).startswith(self.server + "/"):
            raise CalDavError("refusing a calendar resource outside this Nextcloud server")
        return self._request("GET", url, None, depth="0").decode("utf-8")

    def update_resource(self, url, ical):
        if not str(url).startswith(self.server + "/"):
            raise CalDavError("refusing a calendar resource outside this Nextcloud server")
        self._request("PUT", url, ical, depth="0", extra_headers={"Content-Type": "text/calendar; charset=utf-8"})
