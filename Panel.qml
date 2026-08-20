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

  property string activePreset: "tokyo-night-purple"
  property string pendingPreset: ""
  property int selectedIndex: 0
  property string statusText: "Purple baseline active"
  property bool statusError: false
  property string processOutput: ""
  property string processError: ""

  readonly property var presets: [
    {
      id: "tokyo-night-purple",
      label: "Tokyo Night Purple",
      swatches: ["#BB9AF7", "#A000FF", "#D060FF"]
    },
    {
      id: "deep-red",
      label: "Deep Red",
      swatches: ["#8B0000", "#A00000", "#5C0000"]
    },
    {
      id: "bright-white",
      label: "Bright White",
      swatches: ["#FFFFFF", "#E8E8FF", "#D8D8E8"]
    },
    {
      id: "animated-rainbow",
      label: "Animated Rainbow",
      swatches: ["#FF4D6D", "#FFD166", "#06D6A0", "#4CC9F0", "#9B5DE5"]
    }
  ]

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

  function applySelectedPreset() {
    applyPreset(presets[selectedIndex].id)
  }

  function applyPreset(presetId) {
    if (actionProc.running || restoreProc.running) return
    pendingPreset = presetId
    processOutput = ""
    processError = ""
    statusError = false
    statusText = "Applying " + labelForPreset(presetId) + "…"
    actionProc.command = [helperPath, presetId]
    actionProc.running = true
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
    var match = String(output).match(/Preset: ([a-z0-9-]+)/)
    return match ? match[1] : ""
  }

  Component.onCompleted: restoreProc.running = true

  Process {
    id: restoreProc
    command: [root.helperPath, "--restore"]
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: root.processOutput = text.trim()
    }
    stderr: StdioCollector {
      waitForEnd: true
      onStreamFinished: root.processError = text.trim()
    }
    onExited: function(exitCode) {
      var restored = root.presetFromOutput(root.processOutput)
      if (exitCode === 0 && restored !== "") {
        root.statusError = false
        root.activePreset = restored
        root.selectedIndex = root.presetIndex(restored)
        root.statusText = root.labelForPreset(restored) + " restored"
      } else if (exitCode === 75) {
        root.statusError = false
        root.statusText = ""
      } else {
        root.statusError = true
        root.statusText = root.processError !== ""
          ? root.processError
          : "Preset restore failed"
      }
    }
  }

  Process {
    id: actionProc
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

  KeyboardPanel {
    id: panel
    anchorItem: root.anchorItem
    owner: root.barIdentity
    bar: root.bar
    open: root.opened
    focusTarget: keyCatcher
    contentWidth: panel.fittedContentWidth(Style.space(420))
    contentHeight: panel.fittedContentHeight(content.implicitHeight)

    PanelKeyCatcher {
      id: keyCatcher
      anchors.fill: parent
      onMoveRequested: function(dx, dy) {
        var delta = dy !== 0 ? dy : dx
        if (delta === 0) return
        root.selectPreset((root.selectedIndex + delta + root.presets.length) % root.presets.length)
      }
      onActivateRequested: root.applySelectedPreset()
      onCloseRequested: root.close()
      onTabRequested: function(direction) { root.switchPanel(direction) }

      Column {
        id: content
        width: parent.width
        spacing: Style.space(10)

        Text {
          width: parent.width
          text: "OPENRGB PRESETS"
          color: root.contentForeground
          font.family: root.contentFontFamily
          font.pixelSize: Style.font.title
          font.bold: true
          font.letterSpacing: 1.2
        }

        Text {
          width: parent.width
          text: "Choose a RGB lighting preset:"
          color: Qt.rgba(root.contentForeground.r, root.contentForeground.g, root.contentForeground.b, 0.72)
          font.family: root.contentFontFamily
          font.pixelSize: Style.font.body
          wrapMode: Text.WordWrap
        }

        Repeater {
          model: root.presets

          Rectangle {
            id: presetRow
            required property var modelData
            required property int index

            width: content.width
            height: Style.space(44)
            radius: Style.cornerRadius
            color: mouse.containsMouse || root.selectedIndex === index
              ? Qt.rgba(root.contentForeground.r, root.contentForeground.g, root.contentForeground.b, 0.14)
              : Qt.rgba(root.contentForeground.r, root.contentForeground.g, root.contentForeground.b, 0.06)
            border.width: root.activePreset === modelData.id ? 1 : 0
            border.color: root.contentForeground

            Row {
              anchors.fill: parent
              anchors.margins: Style.space(10)
              spacing: Style.space(12)

              Item {
                width: Style.space(62)
                height: parent.height

                Row {
                  anchors.left: parent.left
                  anchors.verticalCenter: parent.verticalCenter
                  spacing: Style.space(3)

                  Repeater {
                    model: presetRow.modelData.swatches
                    Rectangle {
                      required property string modelData
                      width: Style.space(10)
                      height: width
                      radius: width / 2
                      color: modelData
                      border.width: 1
                      border.color: Qt.rgba(1, 1, 1, 0.28)
                    }
                  }
                }
              }

              Text {
                width: parent.width - x
                anchors.verticalCenter: parent.verticalCenter
                text: presetRow.modelData.label
                color: root.contentForeground
                font.family: root.contentFontFamily
                font.pixelSize: Style.font.body
                font.bold: root.activePreset === presetRow.modelData.id
                elide: Text.ElideRight
              }
            }

            MouseArea {
              id: mouse
              anchors.fill: parent
              hoverEnabled: true
              cursorShape: Qt.PointingHandCursor
              enabled: !actionProc.running && !restoreProc.running
              onEntered: root.selectedIndex = presetRow.index
              onClicked: root.applyPreset(presetRow.modelData.id)
            }
          }
        }

        Text {
          visible: root.statusError
          height: visible ? implicitHeight : 0
          width: parent.width
          text: root.statusText
          color: Qt.rgba(root.contentForeground.r, root.contentForeground.g, root.contentForeground.b, 0.7)
          font.family: root.contentFontFamily
          font.pixelSize: Style.font.caption
          wrapMode: Text.WordWrap
        }
      }
    }
  }
}
