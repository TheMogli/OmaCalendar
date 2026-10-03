import unittest
from zoneinfo import ZoneInfo

from omarchy_calendar_sync.caldav import CalDav, CalDavError, normalize_ics


CALENDAR = {"id": "personal", "name": "Personal", "color": "#3584e4"}


class TestIcsNormalization(unittest.TestCase):
    def test_timed_event_and_meeting_link(self):
        raw = """BEGIN:VCALENDAR\r
BEGIN:VEVENT\r
UID:one\r
DTSTART:20260825T100000Z\r
DTEND:20260825T110000Z\r
SUMMARY:Team sync\r
LOCATION:https://meet.example.org/room\r
END:VEVENT\r
END:VCALENDAR\r
"""
        rows = normalize_ics(raw, CALENDAR, ZoneInfo("Europe/Berlin"))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["dateKey"], "2026-08-25")
        self.assertEqual(rows[0]["title"], "Team sync")
        self.assertEqual(rows[0]["meetingUrl"], "https://meet.example.org/room")

    def test_resource_url_is_carried_for_editing(self):
        raw = "BEGIN:VEVENT\nUID:one\nDTSTART:20260825T100000Z\nDTEND:20260825T110000Z\nSUMMARY:Editable\nEND:VEVENT"
        rows = normalize_ics(raw, CALENDAR, ZoneInfo("UTC"), "https://cloud.example.org/event.ics")
        self.assertEqual(rows[0]["resourceUrl"], "https://cloud.example.org/event.ics")

    def test_all_day_event_uses_exclusive_end(self):
        raw = """BEGIN:VCALENDAR
BEGIN:VEVENT
UID:holiday
DTSTART;VALUE=DATE:20260825
DTEND;VALUE=DATE:20260827
SUMMARY:Away
END:VEVENT
END:VCALENDAR
"""
        rows = normalize_ics(raw, CALENDAR, ZoneInfo("Europe/Berlin"))
        self.assertEqual([row["dateKey"] for row in rows], ["2026-08-25", "2026-08-26"])
        self.assertTrue(all(row["allDay"] for row in rows))

    def test_cancelled_event_is_ignored(self):
        raw = "BEGIN:VEVENT\nUID:x\nSTATUS:CANCELLED\nDTSTART:20260825T100000Z\nEND:VEVENT"
        self.assertEqual(normalize_ics(raw, CALENDAR, ZoneInfo("UTC")), [])


class TestClientValidation(unittest.TestCase):
    def test_https_is_required(self):
        with self.assertRaises(CalDavError):
            CalDav("http://cloud.example.org", "david", "secret")

    def test_create_event_uses_uid_and_never_overwrites(self):
        client = CalDav("https://cloud.example.org", "david", "secret")
        calls = []
        client._request = lambda method, url, body, depth="1", extra_headers=None: calls.append(
            (method, url, body, depth, extra_headers)) or b""
        client.create_event({"url": "https://cloud.example.org/cal/personal/"}, "BEGIN:VEVENT\r\nUID:new-id\r\nEND:VEVENT\r\n")
        self.assertEqual(calls[0][0], "PUT")
        self.assertEqual(calls[0][1], "https://cloud.example.org/cal/personal/new-id.ics")
        self.assertEqual(calls[0][4]["If-None-Match"], "*")


if __name__ == "__main__":
    unittest.main()
