# Nextcloud Calendar for Omarchy

A theme-aware replacement for Omarchy's built-in clock with a Nextcloud
agenda. The interface is based on
[tmn73/omarchy-calendar](https://github.com/tmn73/omarchy-calendar), itself a
fork of Omarchy's current clock panel.

![Calendar preview](preview.png)

## Features

- The normal Omarchy clock, date-format cycling, month navigation, ISO weeks,
  and optional year/life progress
- Click a selected day again to add a timed or all-day appointment directly
  to one of your Nextcloud calendars
- The top bar shows an appointment while it is in progress; click an agenda
  row to edit its title, time, all-day state, or location
- Coloured event dots in the month grid and a selected-day agenda
- Next event and live countdown in the panel and bar
- Meeting-link detection for Meet, Zoom, Teams, Webex, and Jitsi URLs
- All Nextcloud calendars discovered automatically; calendars can be hidden
  from the settings page
- Read-only direct CalDAV sync, including recurring events expanded by
  Nextcloud; no Python packages or intermediary service required
- Credentials stored outside the plugin in a mode-600 secret file

## Install for development

```bash
omarchy plugin add <path-to-this-folder> --enable
```

Replace `omarchy.clock` in `~/.config/omarchy/shell.json` with:

```json
{ "id": "david.nextcloud-calendar", "format": "dddd HH:mm" }
```

Also set `bar.centerAnchor` to `david.nextcloud-calendar`, then restart the
shell with `omarchy restart shell`.

## Connect Nextcloud

First create an app password in Nextcloud under **Personal settings → Security
→ Devices & sessions**. Open the clock, select the gear, enter the Nextcloud
URL, username, and app password, then choose **Save and connect**. The plugin
verifies the connection, performs the first sync, and enables its five-minute
timer. The password field is cleared immediately and is never loaded back into
the interface.

For a terminal-based setup instead, run:

```bash
~/.config/omarchy/plugins/david.nextcloud-calendar/sync/setup
```

It asks for your Nextcloud base URL, username, and app password, verifies the
connection immediately, and installs a user timer that refreshes every five
minutes.

Configuration is stored in
`~/.config/omarchy/nextcloud-calendar.json`; the app password is stored
separately in `~/.config/omarchy/nextcloud-calendar.secret`. Both are created
with private permissions. Sync output is written atomically to
`~/.local/state/omarchy/nextcloud-calendar-events.json`.

Example configuration:

```json
{
  "server": "https://cloud.example.com",
  "username": "your-username",
  "passwordFile": "~/.config/omarchy/nextcloud-calendar.secret",
  "calendars": { "include": [], "exclude": [] },
  "window": { "pastDays": 7, "futureDays": 60 }
}
```

An empty `include` list syncs every calendar. Calendar names and IDs may be
used in either list; `exclude` wins.

## Troubleshooting

```bash
~/.config/omarchy/plugins/david.nextcloud-calendar/sync/omarchy-calendar-sync
journalctl --user -u nextcloud-calendar-sync -f
systemctl --user list-timers nextcloud-calendar-sync.timer
```

If authentication fails, generate a new app password and rerun `sync/setup`.
Only HTTPS servers are accepted. The sync is read-only and never creates,
changes, or deletes appointments.

## Development

```bash
cd sync
PYTHONPATH=. python3 -m unittest discover -s ../tests -t .. -v
node --test ../tests/model.test.js
```

MIT licensed. The retained copyright notices are in [LICENSE](LICENSE).
