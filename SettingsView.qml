import QtQuick
import qs.Commons
import qs.Ui

// The calendar's settings page, shown in place of the month grid.
//
// Kept in its own file rather than folded into Panel.qml: the panel is
// already long, and everything here is presentation over values the panel
// owns. This component reads state and emits intent, it never writes
// shell.json itself.
Column {
  id: root

  property color foreground: "white"
  property string fontFamily: ""

  property var calendars: []
  property var hiddenCalendars: []
  property bool showYearProgress: false
  property bool weekStartsMonday: true
  property bool showWorkingLocation: false
  property bool hideDeclined: false
  property int announceLeadMinutes: 15

  property string syncedAt: ""
  property string sourceLabel: ""
  property int eventCount: 0
  property string syncState: "missing"
  property string setupCommand: ""
  property bool setupCommandCopied: false
  property string serverDraft: ""
  property string usernameDraft: ""
  property string passwordDraft: ""
  property bool connecting: false
  property bool connectionError: false
  property string connectionMessage: ""

  signal calendarToggled(string calendarId)
  signal yearProgressToggled()
  signal weekStartToggled()
  signal workingLocationToggled()
  signal hideDeclinedToggled()
  signal leadMinutesPicked(int minutes)
  signal setupCommandCopyRequested()
  signal serverDraftChangedByUser(string value)
  signal usernameDraftChangedByUser(string value)
  signal passwordDraftChangedByUser(string value)
  signal connectRequested()

  readonly property color muted: Qt.darker(foreground, 1.5)
  readonly property color faint: Qt.darker(foreground, 1.9)

  spacing: Style.space(10)

  component SectionTitle: Text {
    color: root.faint
    font.family: root.fontFamily
    font.pixelSize: Style.font.caption
    font.letterSpacing: 1
    font.bold: true
  }

  // A row that reads as a switch without pulling in a control library the
  // rest of this plugin does not use.
  component ToggleRow: Rectangle {
    id: toggle

    property string label: ""
    property string hint: ""
    property bool checked: false
    property color swatch: "transparent"

    signal activated()

    width: parent ? parent.width : 0
    height: toggleBody.height + Style.space(6)
    radius: Style.cornerRadius
    color: hovered.hovered
      ? Qt.rgba(root.foreground.r, root.foreground.g, root.foreground.b, 0.06)
      : "transparent"

    HoverHandler { id: hovered }
    TapHandler { onTapped: toggle.activated() }

    Row {
      id: toggleBody
      anchors.left: parent.left
      anchors.right: parent.right
      anchors.leftMargin: Style.space(3)
      anchors.rightMargin: Style.space(3)
      anchors.verticalCenter: parent.verticalCenter
      spacing: Style.space(4)

      Text {
        anchors.verticalCenter: parent.verticalCenter
        width: Style.space(14)
        text: toggle.checked ? "✓" : ""
        color: root.foreground
        font.family: root.fontFamily
        font.pixelSize: Style.font.bodySmall
      }

      Rectangle {
        anchors.verticalCenter: parent.verticalCenter
        visible: toggle.swatch != "transparent"
        width: Style.space(4)
        height: width
        radius: width / 2
        color: toggle.checked ? toggle.swatch : "transparent"
        border.width: Style.spacing.hairline
        border.color: toggle.swatch
      }

      Column {
        anchors.verticalCenter: parent.verticalCenter
        width: toggleBody.width - Style.space(26)
        spacing: Style.space(1)

        Text {
          width: parent.width
          text: toggle.label
          color: toggle.checked ? root.foreground : root.muted
          font.family: root.fontFamily
          font.pixelSize: Style.font.bodySmall
          elide: Text.ElideRight
        }

        Text {
          width: parent.width
          visible: toggle.hint !== ""
          text: toggle.hint
          color: root.faint
          font.family: root.fontFamily
          font.pixelSize: Style.font.caption
          elide: Text.ElideRight
        }
      }
    }
  }

  // ---- Calendars

  SectionTitle { text: qsTr("CALENDARS") }

  Text {
    width: parent.width
    visible: root.calendars.length === 0
    text: qsTr("Nothing synced yet, so there is nothing to choose from.")
    color: root.faint
    font.family: root.fontFamily
    font.pixelSize: Style.font.caption
    wrapMode: Text.WordWrap
  }

  Repeater {
    model: root.calendars

    ToggleRow {
      required property var modelData

      label: modelData.name
      swatch: modelData.color
      checked: root.hiddenCalendars.indexOf(modelData.id) === -1
      onActivated: root.calendarToggled(modelData.id)
    }
  }

  // ---- Display

  SectionTitle { text: qsTr("DISPLAY") }

  ToggleRow {
    label: qsTr("Week starts on Monday")
    hint: qsTr("Off starts the week on Sunday")
    checked: root.weekStartsMonday
    onActivated: root.weekStartToggled()
  }

  ToggleRow {
    label: qsTr("Working location events")
    hint: qsTr("Availability markers such as work-from-home, hidden by default")
    checked: root.showWorkingLocation
    onActivated: root.workingLocationToggled()
  }

  ToggleRow {
    // Every row on this page reads "checked means shown". Phrasing this one as
    // "Hide ..." inverted that and made the page contradict itself.
    label: qsTr("Declined invitations")
    hint: qsTr("Shown struck through when on")
    checked: !root.hideDeclined
    onActivated: root.hideDeclinedToggled()
  }

  ToggleRow {
    label: qsTr("Year and life progress")
    hint: qsTr("The upstream clock's bars, off by default")
    checked: root.showYearProgress
    onActivated: root.yearProgressToggled()
  }

  // ---- Bar

  SectionTitle { text: qsTr("BAR LABEL") }

  Text {
    width: parent.width
    text: qsTr("How early the bar gives up the clock to announce what is next.")
    color: root.faint
    font.family: root.fontFamily
    font.pixelSize: Style.font.caption
    wrapMode: Text.WordWrap
  }

  Row {
    spacing: Style.space(3)

    Repeater {
      model: [0, 5, 15, 30, 60]

      Rectangle {
        required property var modelData

        readonly property bool active: modelData === root.announceLeadMinutes

        width: leadLabel.width + Style.space(8)
        height: leadLabel.height + Style.space(4)
        radius: height / 2
        color: active
          ? Qt.rgba(root.foreground.r, root.foreground.g, root.foreground.b, 0.14)
          : "transparent"
        border.width: Style.spacing.hairline
        border.color: active ? root.muted : Qt.darker(root.foreground, 2.4)

        Text {
          id: leadLabel
          anchors.centerIn: parent
          text: modelData === 0 ? qsTr("Never") : modelData + qsTr("min")
          color: active ? root.foreground : root.faint
          font.family: root.fontFamily
          font.pixelSize: Style.font.caption
        }

        TapHandler { onTapped: root.leadMinutesPicked(modelData) }
      }
    }
  }

  // ---- Connection and sync

  SectionTitle { text: qsTr("NEXTCLOUD") }

  TextField {
    width: parent.width
    text: root.serverDraft
    placeholderText: qsTr("https://cloud.example.com")
    foreground: root.foreground
    accent: Color.accent
    font.family: root.fontFamily
    onTextChanged: root.serverDraftChangedByUser(text)
  }

  TextField {
    width: parent.width
    text: root.usernameDraft
    placeholderText: qsTr("Username")
    foreground: root.foreground
    accent: Color.accent
    font.family: root.fontFamily
    onTextChanged: root.usernameDraftChangedByUser(text)
  }

  TextField {
    width: parent.width
    text: root.passwordDraft
    placeholderText: qsTr("App password (leave blank to keep saved password)")
    password: true
    foreground: root.foreground
    accent: Color.accent
    font.family: root.fontFamily
    onTextChanged: root.passwordDraftChangedByUser(text)
  }

  Rectangle {
    width: connectLabel.implicitWidth + Style.space(16)
    height: connectLabel.implicitHeight + Style.space(8)
    radius: height / 2
    color: connectHover.hovered ? Qt.rgba(root.foreground.r, root.foreground.g, root.foreground.b, 0.16) : Qt.rgba(root.foreground.r, root.foreground.g, root.foreground.b, 0.10)
    opacity: root.connecting ? 0.55 : 1
    HoverHandler { id: connectHover; cursorShape: Qt.PointingHandCursor }
    TapHandler { enabled: !root.connecting; onTapped: root.connectRequested() }
    Text {
      id: connectLabel
      anchors.centerIn: parent
      text: root.connecting ? qsTr("Connecting…") : qsTr("Save and connect")
      color: root.foreground
      font.family: root.fontFamily
      font.pixelSize: Style.font.caption
    }
  }

  Text {
    width: parent.width
    visible: root.connectionMessage !== ""
    text: root.connectionMessage
    color: root.connectionError ? Color.accent : root.muted
    font.family: root.fontFamily
    font.pixelSize: Style.font.caption
    wrapMode: Text.WordWrap
  }

  SectionTitle { text: qsTr("SYNC STATUS") }

  Text {
    width: parent.width
    color: root.syncState === "missing" && syncHover.hovered ? root.foreground : root.faint
    font.family: root.fontFamily
    font.pixelSize: Style.font.caption
    wrapMode: Text.WordWrap

    HoverHandler {
      id: syncHover
      enabled: root.syncState === "missing"
      cursorShape: Qt.PointingHandCursor
    }

    TapHandler {
      enabled: root.syncState === "missing"
      onTapped: root.setupCommandCopyRequested()
    }

    text: {
      if (root.syncState === "missing") {
        return root.setupCommandCopied
          ? qsTr("Copied. Paste it in a terminal:\n%1").arg(root.setupCommand)
          : qsTr("No calendar connected yet. Click to copy, then run:\n%1").arg(root.setupCommand)
      }
      if (root.syncState === "version") return qsTr("The events file was written by a newer version of this plugin.")

      var line = root.eventCount + qsTr(" events from ") + root.sourceLabel
      if (root.syncState === "stale") {
        return line + qsTr("\nLast sync looks old. Check: journalctl --user -u nextcloud-calendar-sync")
      }
      return line + qsTr("\nLast sync ") + root.syncedAt
    }
  }
}
