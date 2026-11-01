import QtQuick
import Quickshell
import Quickshell.Io
import qs.Commons
import qs.Ui

Panel {
  id: root
  moduleName: "io.github.ol4vr.openrgb-presets"
  manageIpc: false

  property var anchorItem: null
  property var hostWidget: null
  readonly property var barIdentity: hostWidget || root
  readonly property string helperPath: Quickshell.env("HOME")
    + "/.config/omarchy/plugins/io.github.ol4vr.openrgb-presets/apply-preset"
  readonly property color contentForeground: bar ? bar.foreground : Color.foreground
  readonly property string contentFontFamily: bar ? bar.fontFamily : Style.font.family

  property string activePreset: "electric-sunrise"
  property string pendingPreset: ""
  property int selectedIndex: 7
  property string statusText: "Electric Sunrise active"
  property bool statusError: false
  property string processOutput: ""
  property string processError: ""
  property bool ramLightingEnabled: true
  property string ramPendingState: ""
  property string ramOutput: ""
  property string ramError: ""

  readonly property var presets: [
    {
      id: "deep-red",
      label: "Deep Red",
      kind: "STATIC",
      detail: "LOW-LIGHT FOCUS",
      accent: "#F7768E",
      swatches: ["#8B0000", "#A00000", "#5C0000"]
    },
    {
      id: "deep-blue",
      label: "Deep Blue",
      kind: "STATIC",
      detail: "DEEP BLUE",
      accent: "#000B22",
      swatches: ["#000B22"]
    },
    {
      id: "bright-white",
      label: "Bright White",
      kind: "STATIC",
      detail: "CLEAR DESK LIGHT",
      accent: "#C0CAF5",
      swatches: ["#FFFFFF", "#E8E8FF", "#D8D8E8"]
    },
    {
      id: "animated-rainbow",
      label: "Animated Rainbow",
      kind: "HARDWARE",
      detail: "CONTROLLER EFFECT",
      accent: "#BB9AF7",
      swatches: ["#FF4D6D", "#FFD166", "#06D6A0", "#4CC9F0", "#9B5DE5"]
    },
    {
      id: "neon-rain",
      label: "Neon Rain",
      kind: "EFFECTS",
      detail: "FIVE-COLOR RAIN",
      accent: "#7DCFFF",
      swatches: ["#FF0055", "#8CFF00", "#00D4FF"]
    },
    {
      id: "aurora-comet",
      label: "Aurora Comet",
      kind: "EFFECTS",
      detail: "GREEN COMET",
      accent: "#9ECE6A",
      swatches: ["#95FF00", "#00D4FF", "#8A2BE2"]
    },
    {
      id: "spectrum-wave",
      label: "Spectrum Wave",
      kind: "EFFECTS",
      detail: "SYNCED RAINBOW",
      accent: "#7AA2F7",
      swatches: ["#FF4D6D", "#FFD166", "#06D6A0", "#4CC9F0", "#9B5DE5"]
    },
    {
      id: "electric-sunrise",
      label: "Electric Sunrise",
      kind: "EFFECTS",
      detail: "BLUE · RED · ORANGE",
      accent: "#E0AF68",
      swatches: ["#4000FF", "#FF003C", "#FF4400"]
    },
    {
      id: "matte-black-orange",
      label: "Matte Black Orange",
      kind: "EFFECTS",
      detail: "ORANGE · RED · BURNT",
      accent: "#FF4400",
      swatches: ["#FF4400", "#E83B00", "#C92B00"]
    },
    {
      id: "black",
      label: "Black (Turn Off RGB)",
      kind: "OFF",
      detail: "ALL CONTROLLERS",
      accent: "#565F89",
      swatches: ["#000000", "#101018", "#20202A"]
    },
    {
      id: "horde-red",
      label: "Horde Red",
      kind: "EFFECTS",
      detail: "RED · DEEP · DARK",
      accent: "#8B0000",
      swatches: ["#8B0000", "#680000", "#4A0000"]
    },
    {
      id: "alliance-blue",
      label: "Alliance Blue",
      kind: "EFFECTS",
      detail: "BLUE · MID · DARK",
      accent: "#0033AA",
      swatches: ["#0033AA", "#002788", "#001A66"]
    }
  ]

  readonly property var activePresetData: {
    for (var i = 0; i < presets.length; i++) {
      if (presets[i].id === activePreset) return presets[i]
    }
    return presets[0]
  }

  readonly property string activePresetLabel: {
    for (var i = 0; i < presets.length; i++) {
      if (presets[i].id === activePreset) return presets[i].label
    }
    return "Unknown"
  }

  function open() {
    root.controller.show()
    Qt.callLater(function() { keyCatcher.forceActiveFocus() })
  }

  function close() {
    root.controller.hide()
  }

  function toggle() {
    if (root.opened) root.close()
    else root.open()
  }

  function switchPanel(direction) {
    if (root.bar && typeof root.bar.switchPanelFrom === "function")
      return root.bar.switchPanelFrom(root.barIdentity, direction)
    return false
  }

  function selectPreset(index) {
    if (index < 0 || index >= presets.length) return
    selectedIndex = index
  }

  function moveSelection(dx, dy) {
    if (dy === 0) {
      selectPreset((selectedIndex + dx + presets.length) % presets.length)
      return
    }

    var columns = 2
    var rows = Math.ceil(presets.length / columns)
    var column = selectedIndex % columns
    var row = Math.floor(selectedIndex / columns)
    var nextRow = (row + dy + rows) % rows
    var nextIndex = nextRow * columns + column
    while (nextIndex >= presets.length) {
      nextRow = (nextRow + dy + rows) % rows
      nextIndex = nextRow * columns + column
    }
    selectPreset(nextIndex)
  }

  function applySelectedPreset() {
    applyPreset(presets[selectedIndex].id)
  }

  function applyPreset(presetId) {
    if (actionProc.running || currentProc.running || ramActionProc.running) return
    pendingPreset = presetId
    processOutput = ""
    processError = ""
    statusError = false
    statusText = "Applying " + labelForPreset(presetId) + "…"
    actionProc.running = true
  }

  function toggleRamLighting() {
    if (actionProc.running || currentProc.running || ramActionProc.running) return
    ramPendingState = ramLightingEnabled ? "off" : "on"
    ramOutput = ""
    ramError = ""
    statusError = false
    statusText = ramPendingState === "on"
      ? "Restoring static RAM lighting…"
      : "Setting RAM lighting to static black…"
    ramActionProc.running = true
  }

  function labelForPreset(presetId) {
    for (var i = 0; i < presets.length; i++) {
      if (presets[i].id === presetId) return presets[i].label
    }
    return presetId
  }

  function presetIndex(presetId) {
    for (var i = 0; i < presets.length; i++) {
      if (presets[i].id === presetId) return i
    }
    return 0
  }

  function presetFromOutput(output) {
    var value = String(output).trim()
    var match = value.match(/^Preset: ([a-z0-9-]+)$/)
    return match ? match[1] : value.match(/^[a-z0-9-]+$/) ? value : ""
  }

  Component.onCompleted: {
    currentProc.running = true
    ramCurrentProc.running = true
  }

  Process {
    id: currentProc
    command: [root.helperPath, "--current"]
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: root.processOutput = text.trim()
    }
    stderr: StdioCollector {
      waitForEnd: true
      onStreamFinished: root.processError = text.trim()
    }
    onExited: function(exitCode) {
      var current = root.presetFromOutput(root.processOutput)
      if (exitCode === 0 && current !== "") {
        root.statusError = false
        root.activePreset = current
        root.selectedIndex = root.presetIndex(current)
        root.statusText = root.labelForPreset(current) + " active"
      } else {
        root.statusError = true
        root.statusText = root.processError !== ""
          ? root.processError
          : "Preset state read failed"
      }
    }
  }

  Process {
    id: actionProc
    command: [root.helperPath, root.pendingPreset]
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: root.processOutput = text.trim()
    }
    stderr: StdioCollector {
      waitForEnd: true
      onStreamFinished: root.processError = text.trim()
    }
    onExited: function(exitCode) {
      if (exitCode === 0) {
        root.statusError = false
        root.activePreset = root.pendingPreset
        root.selectedIndex = root.presetIndex(root.pendingPreset)
        root.statusText = root.labelForPreset(root.pendingPreset) + " active"
      } else {
        root.statusError = true
        root.statusText = root.processError !== ""
          ? root.processError
          : "Preset application failed"
      }
      root.pendingPreset = ""
    }
  }

  Process {
    id: ramCurrentProc
    command: [root.helperPath, "--ram-current"]
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: root.ramOutput = text.trim()
    }
    stderr: StdioCollector {
      waitForEnd: true
      onStreamFinished: root.ramError = text.trim()
    }
    onExited: function(exitCode) {
      if (exitCode === 0 && (root.ramOutput === "on" || root.ramOutput === "off")) {
        root.ramLightingEnabled = root.ramOutput === "on"
      } else {
        root.statusError = true
        root.statusText = root.ramError !== ""
          ? root.ramError
          : "RAM lighting preference read failed"
      }
    }
  }

  Process {
    id: ramActionProc
    command: [
      root.helperPath,
      root.ramPendingState === "on" ? "--ram-on" : "--ram-off"
    ]
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: root.ramOutput = text.trim()
    }
    stderr: StdioCollector {
      waitForEnd: true
      onStreamFinished: root.ramError = text.trim()
    }
    onExited: function(exitCode) {
      if (exitCode === 0) {
        root.ramLightingEnabled = root.ramPendingState === "on"
        root.statusError = false
        root.statusText = root.ramLightingEnabled
          ? "Static RAM lighting restored"
          : "RAM lighting set to static black"
      } else {
        root.statusError = true
        root.statusText = root.ramError !== ""
          ? root.ramError
          : "RAM lighting change failed"
      }
      root.ramPendingState = ""
    }
  }

  KeyboardPanel {
    id: panel
    anchorItem: root.anchorItem
    owner: root.barIdentity
    bar: root.bar
    open: root.opened
    focusTarget: keyCatcher
    contentWidth: panel.fittedContentWidth(Style.space(500))
    contentHeight: panel.fittedContentHeight(content.implicitHeight)

    PanelKeyCatcher {
      id: keyCatcher
      anchors.fill: parent
      onMoveRequested: function(dx, dy) {
        if (dx === 0 && dy === 0) return
        root.moveSelection(dx, dy)
      }
      onActivateRequested: root.applySelectedPreset()
      onCloseRequested: root.close()
      onTabRequested: function(direction) { root.switchPanel(direction) }

      Column {
        id: content
        width: parent.width
        spacing: Style.space(12)

        Row {
          width: parent.width
          spacing: Style.space(8)

          Text {
            text: "󱩒"
            color: "#7AA2F7"
            font.family: root.contentFontFamily
            font.pixelSize: Style.font.title
          }

          Text {
            text: "LIGHTING CONTROL"
            color: root.contentForeground
            font.family: root.contentFontFamily
            font.pixelSize: Style.font.title
            font.bold: true
            font.letterSpacing: 1.2
          }
        }

        Rectangle {
          id: activeCard
          readonly property color accentColor: root.activePresetData.accent

          width: parent.width
          height: Style.space(104)
          radius: Style.cornerRadius
          color: Qt.rgba(accentColor.r, accentColor.g, accentColor.b, 0.09)
          border.width: 1
          border.color: Qt.rgba(accentColor.r, accentColor.g, accentColor.b, 0.42)

          Rectangle {
            width: Style.space(3)
            anchors.left: parent.left
            anchors.top: parent.top
            anchors.bottom: parent.bottom
            color: activeCard.accentColor
          }

          Text {
            id: activeIcon
            anchors.left: parent.left
            anchors.leftMargin: Style.space(18)
            anchors.verticalCenter: parent.verticalCenter
            text: "󱩒"
            color: activeCard.accentColor
            font.family: root.contentFontFamily
            font.pixelSize: Style.space(42)
          }

          Column {
            anchors.left: activeIcon.right
            anchors.leftMargin: Style.space(16)
            anchors.right: activeMeta.left
            anchors.rightMargin: Style.space(12)
            anchors.verticalCenter: parent.verticalCenter
            spacing: Style.space(3)

            Text {
              width: parent.width
              text: actionProc.running ? "APPLYING PRESET" : "ACTIVE PRESET"
              color: Qt.rgba(root.contentForeground.r, root.contentForeground.g, root.contentForeground.b, 0.58)
              font.family: root.contentFontFamily
              font.pixelSize: Style.font.caption
              font.letterSpacing: 1.1
            }

            Text {
              width: parent.width
              text: actionProc.running
                ? root.labelForPreset(root.pendingPreset)
                : root.activePresetLabel
              color: root.contentForeground
              font.family: root.contentFontFamily
              font.pixelSize: Style.font.title
              font.bold: true
              elide: Text.ElideRight
            }

            Text {
              width: parent.width
              text: actionProc.running
                ? "UPDATING HUGIN LIGHTING"
                : root.activePresetData.detail
              color: activeCard.accentColor
              font.family: root.contentFontFamily
              font.pixelSize: Style.font.caption
              font.letterSpacing: 0.8
              elide: Text.ElideRight
            }
          }

          Column {
            id: activeMeta
            width: Style.space(112)
            anchors.right: parent.right
            anchors.rightMargin: Style.space(16)
            anchors.verticalCenter: parent.verticalCenter
            spacing: Style.space(12)

            Rectangle {
              anchors.horizontalCenter: parent.horizontalCenter
              width: activeKind.implicitWidth + Style.space(18)
              height: Style.space(24)
              radius: Style.cornerRadius
              color: Qt.rgba(activeCard.accentColor.r, activeCard.accentColor.g, activeCard.accentColor.b, 0.14)
              border.width: 1
              border.color: Qt.rgba(activeCard.accentColor.r, activeCard.accentColor.g, activeCard.accentColor.b, 0.35)

              Text {
                id: activeKind
                anchors.centerIn: parent
                text: actionProc.running ? "APPLYING" : root.activePresetData.kind
                color: activeCard.accentColor
                font.family: root.contentFontFamily
                font.pixelSize: Style.font.caption
                font.bold: true
                font.letterSpacing: 0.8
              }
            }

            Row {
              anchors.horizontalCenter: parent.horizontalCenter
              spacing: Style.space(4)

              Repeater {
                model: root.activePresetData.swatches

                Rectangle {
                  required property string modelData
                  width: Style.space(11)
                  height: width
                  radius: width / 2
                  color: modelData
                  border.width: 1
                  border.color: Qt.rgba(1, 1, 1, 0.30)
                }
              }
            }
          }
        }

        Rectangle {
          id: ramToggle
          width: parent.width
          height: Style.space(58)
          radius: Style.cornerRadius
          color: Qt.rgba(root.contentForeground.r, root.contentForeground.g,
            root.contentForeground.b, 0.055)
          border.width: 1
          border.color: Qt.rgba(root.contentForeground.r, root.contentForeground.g,
            root.contentForeground.b, 0.18)

          Column {
            anchors.left: parent.left
            anchors.leftMargin: Style.space(14)
            anchors.verticalCenter: parent.verticalCenter
            spacing: Style.space(2)

            Text {
              text: "RAM LIGHTING"
              color: root.contentForeground
              font.family: root.contentFontFamily
              font.pixelSize: Style.font.body
              font.bold: true
              font.letterSpacing: 0.8
            }

            Text {
              text: root.ramLightingEnabled
                ? "STATIC PRESET COLOR"
                : "STATIC BLACK"
              color: root.ramLightingEnabled ? "#9ECE6A" : "#565F89"
              font.family: root.contentFontFamily
              font.pixelSize: Style.font.caption
              font.letterSpacing: 0.7
            }
          }

          Rectangle {
            width: Style.space(54)
            height: Style.space(28)
            radius: height / 2
            anchors.right: parent.right
            anchors.rightMargin: Style.space(14)
            anchors.verticalCenter: parent.verticalCenter
            color: root.ramLightingEnabled ? "#9ECE6A" : "#3B4261"
            opacity: ramActionProc.running ? 0.55 : 1

            Rectangle {
              width: Style.space(22)
              height: width
              radius: width / 2
              anchors.verticalCenter: parent.verticalCenter
              x: root.ramLightingEnabled
                ? parent.width - width - Style.space(3)
                : Style.space(3)
              color: "#FFFFFF"
            }
          }

          MouseArea {
            anchors.fill: parent
            cursorShape: Qt.PointingHandCursor
            enabled: !actionProc.running && !currentProc.running && !ramActionProc.running
            onClicked: root.toggleRamLighting()
          }
        }

        Rectangle {
          width: parent.width
          height: 1
          color: Qt.rgba(root.contentForeground.r, root.contentForeground.g, root.contentForeground.b, 0.12)
        }

        Row {
          width: parent.width
          spacing: Style.space(8)

          Text {
            text: "✦"
            color: "#7AA2F7"
            font.family: root.contentFontFamily
            font.pixelSize: Style.font.body
          }

          Text {
            text: "PRESET LIBRARY"
            color: root.contentForeground
            font.family: root.contentFontFamily
            font.pixelSize: Style.font.body
            font.bold: true
            font.letterSpacing: 1.1
          }
        }

        Grid {
          id: presetGrid
          width: parent.width
          columns: 2
          columnSpacing: Style.space(10)
          rowSpacing: Style.space(10)
          readonly property real cardWidth: (width - columnSpacing) / 2

          Repeater {
            model: root.presets

            Rectangle {
              id: presetCard
              required property var modelData
              required property int index
              readonly property bool isActive: root.activePreset === modelData.id
              readonly property bool isSelected: root.selectedIndex === index
              readonly property color accentColor: modelData.accent

              width: presetGrid.cardWidth
              height: Style.space(82)
              radius: Style.cornerRadius
              color: isActive
                ? Qt.rgba(accentColor.r, accentColor.g, accentColor.b, 0.11)
                : mouse.containsMouse || isSelected
                  ? Qt.rgba(root.contentForeground.r, root.contentForeground.g, root.contentForeground.b, 0.11)
                  : Qt.rgba(root.contentForeground.r, root.contentForeground.g, root.contentForeground.b, 0.055)
              border.width: isActive || isSelected ? 1 : 0
              border.color: isActive
                ? Qt.rgba(accentColor.r, accentColor.g, accentColor.b, 0.62)
                : Qt.rgba(root.contentForeground.r, root.contentForeground.g, root.contentForeground.b, 0.34)

              Rectangle {
                anchors.left: parent.left
                anchors.top: parent.top
                anchors.right: parent.right
                height: Style.space(2)
                color: presetCard.accentColor
                opacity: presetCard.isActive ? 0.9 : mouse.containsMouse ? 0.55 : 0.22
              }

              Row {
                id: cardSwatches
                anchors.left: parent.left
                anchors.leftMargin: Style.space(12)
                anchors.top: parent.top
                anchors.topMargin: Style.space(13)
                spacing: Style.space(3)

                Repeater {
                  model: presetCard.modelData.swatches

                  Rectangle {
                    required property string modelData
                    width: Style.space(9)
                    height: width
                    radius: width / 2
                    color: modelData
                    border.width: 1
                    border.color: Qt.rgba(1, 1, 1, 0.26)
                  }
                }
              }

              Rectangle {
                anchors.right: parent.right
                anchors.rightMargin: Style.space(10)
                anchors.verticalCenter: cardSwatches.verticalCenter
                width: cardKind.implicitWidth + Style.space(12)
                height: Style.space(18)
                radius: Style.cornerRadius
                color: Qt.rgba(presetCard.accentColor.r, presetCard.accentColor.g, presetCard.accentColor.b, 0.10)

                Text {
                  id: cardKind
                  anchors.centerIn: parent
                  text: presetCard.isActive ? "ACTIVE" : presetCard.modelData.kind
                  color: presetCard.accentColor
                  font.family: root.contentFontFamily
                  font.pixelSize: Style.font.caption
                  font.bold: presetCard.isActive
                  font.letterSpacing: 0.6
                }
              }

              Text {
                anchors.left: parent.left
                anchors.leftMargin: Style.space(12)
                anchors.right: parent.right
                anchors.rightMargin: Style.space(12)
                anchors.top: cardSwatches.bottom
                anchors.topMargin: Style.space(8)
                text: presetCard.modelData.label
                color: root.contentForeground
                font.family: root.contentFontFamily
                font.pixelSize: Style.font.body
                font.bold: presetCard.isActive
                elide: Text.ElideRight
              }

              Text {
                anchors.left: parent.left
                anchors.leftMargin: Style.space(12)
                anchors.right: parent.right
                anchors.rightMargin: Style.space(12)
                anchors.bottom: parent.bottom
                anchors.bottomMargin: Style.space(9)
                text: presetCard.modelData.detail
                color: presetCard.accentColor
                opacity: 0.82
                font.family: root.contentFontFamily
                font.pixelSize: Style.font.caption
                font.letterSpacing: 0.7
                elide: Text.ElideRight
              }

              MouseArea {
                id: mouse
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                enabled: !actionProc.running && !currentProc.running && !ramActionProc.running
                onEntered: root.selectedIndex = presetCard.index
                onClicked: root.applyPreset(presetCard.modelData.id)
              }
            }
          }
        }

        Rectangle {
          visible: root.statusError
          height: visible ? errorText.implicitHeight + Style.space(20) : 0
          width: parent.width
          radius: Style.cornerRadius
          color: Qt.rgba(0.97, 0.46, 0.56, 0.10)
          border.width: visible ? 1 : 0
          border.color: Qt.rgba(0.97, 0.46, 0.56, 0.35)

          Text {
            id: errorText
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.verticalCenter: parent.verticalCenter
            anchors.margins: Style.space(10)
            text: root.statusText
            color: "#F7768E"
            font.family: root.contentFontFamily
            font.pixelSize: Style.font.caption
            wrapMode: Text.WordWrap
          }
        }

        Text {
          width: parent.width
          text: "ARROWS  SELECT    ·    ENTER  APPLY"
          color: Qt.rgba(root.contentForeground.r, root.contentForeground.g, root.contentForeground.b, 0.42)
          font.family: root.contentFontFamily
          font.pixelSize: Style.font.caption
          font.letterSpacing: 0.8
          horizontalAlignment: Text.AlignHCenter
        }
      }
    }
  }
}
