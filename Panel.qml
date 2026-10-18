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
  readonly property string tetrisHelperPath: Quickshell.env("HOME")
    + "/.config/omarchy/plugins/io.github.ol4vr.openrgb-presets/ram-tetris"
  readonly property string recoveryHelperPath: Quickshell.env("HOME")
    + "/.config/omarchy/plugins/io.github.ol4vr.openrgb-presets/lighting-recovery"
  readonly property color contentForeground: bar ? bar.foreground : Color.foreground
  readonly property string contentFontFamily: bar ? bar.fontFamily : Style.font.family

  property string activePreset: "bright-white"
  property string pendingPreset: ""
  property int selectedIndex: 0
  property string statusText: "Static White active"
  property bool statusError: false
  property string processOutput: ""
  property string processError: ""
  property bool ramTetrisPreference: false
  property string ramTetrisState: "off"
  property string ramTetrisMessage: "Static DDR5 lighting"
  property string tetrisPendingAction: ""
  property string tetrisProcessOutput: ""
  property string tetrisProcessError: ""
  property bool lightingFailure: false
  property string failureScope: ""
  property string failureCode: ""
  property string failureDescription: ""
  property string failureReason: ""
  property string failureReference: ""
  property string failureTimestamp: ""
  property string failureSubsystem: ""
  property string recoveryStatus: ""
  property string recoverySummary: ""
  property string recoveryAction: ""
  property string recoveryToken: ""
  property string recoveryFeedback: ""
  property bool recoveryAttemptActive: false
  property bool recoveryAttemptBlocked: false
  property bool diagnosticsExpanded: false
  property string recoveryProcessOutput: ""
  property string recoveryProcessError: ""

  readonly property var presets: [
    {
      id: "deep-red",
      label: "Static Red",
      kind: "STATIC",
      mode: "STATIC COLOR",
      detail: "LOW-LIGHT FOCUS",
      accent: "#F7768E",
      swatches: ["#8B0000", "#A00000", "#5C0000"]
    },
    {
      id: "deep-blue",
      label: "Static Blue",
      kind: "STATIC",
      mode: "STATIC COLOR",
      detail: "DEEP BLUE",
      accent: "#7AA2F7",
      swatches: ["#000B22"]
    },
    {
      id: "bright-white",
      label: "Static White",
      kind: "STATIC",
      mode: "STATIC COLOR",
      detail: "CLEAR DESK LIGHT",
      accent: "#C0CAF5",
      swatches: ["#FFFFFF", "#E8E8FF", "#D8D8E8"]
    },
    {
      id: "animated-rainbow",
      label: "Animated Rainbow",
      kind: "HARDWARE",
      mode: "RAINBOW",
      detail: "CONTROLLER EFFECT",
      accent: "#BB9AF7",
      swatches: ["#FF4D6D", "#FFD166", "#06D6A0", "#4CC9F0", "#9B5DE5"]
    },
    {
      id: "neon-rain",
      label: "Neon Rain",
      kind: "EFFECTS",
      mode: "RAIN",
      detail: "FIVE-COLOR RAIN",
      accent: "#7DCFFF",
      swatches: ["#FF0055", "#8CFF00", "#00D4FF"]
    },
    {
      id: "aurora-comet",
      label: "Aurora Comet",
      kind: "EFFECTS",
      mode: "COMET",
      detail: "GREEN COMET",
      accent: "#9ECE6A",
      swatches: ["#95FF00", "#00D4FF", "#8A2BE2"]
    },
    {
      id: "spectrum-wave",
      label: "Spectrum Wave",
      kind: "EFFECTS",
      mode: "RAINBOW WAVE",
      detail: "SYNCED RAINBOW",
      accent: "#7AA2F7",
      swatches: ["#FF4D6D", "#FFD166", "#06D6A0", "#4CC9F0", "#9B5DE5"]
    },
    {
      id: "electric-sunrise",
      label: "Electric Sunrise",
      kind: "EFFECTS",
      mode: "SUNRISE",
      detail: "BLUE · RED · ORANGE",
      accent: "#E0AF68",
      swatches: ["#4000FF", "#FF003C", "#FF4400"]
    },
    {
      id: "matte-black-orange",
      label: "Matte Black Orange",
      kind: "EFFECTS",
      mode: "SUNRISE",
      detail: "ORANGE · RED · BURNT",
      accent: "#FF4400",
      swatches: ["#FF4400", "#E83B00", "#C92B00"]
    },
    {
      id: "black",
      label: "Black (Turn Off RGB)",
      kind: "OFF",
      mode: "LIGHTS OFF",
      detail: "ALL CONTROLLERS",
      accent: "#A9B1D6",
      swatches: ["#000000", "#101018", "#20202A"]
    },
    {
      id: "horde-red",
      label: "For the Horde!",
      kind: "EFFECTS",
      mode: "SUNRISE",
      detail: "RED · DEEP · DARK",
      accent: "#F7768E",
      swatches: ["#8B0000", "#680000", "#4A0000"]
    },
    {
      id: "alliance-blue",
      label: "For the Alliance!",
      kind: "EFFECTS",
      mode: "SUNRISE",
      detail: "BLUE · MID · DARK",
      accent: "#7AA2F7",
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
    if (!tetrisStatusProc.running) tetrisStatusProc.running = true
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
    if (actionProc.running || currentProc.running) return
    pendingPreset = presetId
    processOutput = ""
    processError = ""
    statusError = false
    statusText = "Applying " + labelForPreset(presetId) + "…"
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
    var value = String(output).trim()
    var match = value.match(/^Preset: ([a-z0-9-]+)$/)
    return match ? match[1] : value.match(/^[a-z0-9-]+$/) ? value : ""
  }

  function toggleRamTetris() {
    if (lightingFailure || tetrisActionProc.running || tetrisStatusProc.running
        || recoveryProc.running || actionProc.running)
      return
    tetrisPendingAction = ramTetrisPreference ? "disable" : "enable"
    tetrisProcessOutput = ""
    tetrisProcessError = ""
    tetrisActionProc.running = true
  }

  function applyTetrisStatus(output) {
    try {
      var state = JSON.parse(String(output).trim())
      var previousReference = failureReference
      ramTetrisPreference = state.preference === true
      ramTetrisState = String(state.state || "waiting")
      ramTetrisMessage = String(state.message || "RAM Tetris status unavailable")
      lightingFailure = state.failure === true
      failureScope = String(state.scope || "")
      failureCode = String(state.code || "")
      failureDescription = String(state.description || "")
      failureReason = String(state.message || "")
      failureReference = String(state.incident_reference || "")
      failureTimestamp = String(state.first_detected || "Unknown")
      failureSubsystem = String(state.subsystem || "unknown")
      recoveryStatus = String(state.recovery_status || "")
      recoverySummary = String(state.recovery_summary || "")
      if (previousReference !== "" && previousReference !== failureReference) {
        recoveryFeedback = ""
        recoveryAttemptBlocked = false
      }
      if (!lightingFailure) {
        recoveryAttemptActive = false
        recoveryAttemptBlocked = false
        recoveryToken = ""
      }
    } catch (error) {
      ramTetrisState = "failed"
      ramTetrisMessage = "RAM Tetris status response was invalid"
      lightingFailure = true
      failureScope = "lighting"
      failureCode = "LGT-UNK-000"
      failureDescription = "Lighting status could not be read."
      failureReason = ramTetrisMessage
      failureReference = "Unavailable"
      failureTimestamp = "Unknown"
      failureSubsystem = "unknown"
      recoveryStatus = "manual-review"
      recoverySummary = "Manual review is required."
    }
  }

  function beginRecovery() {
    if (!lightingFailure || recoveryProc.running || recoveryAttemptActive)
      return
    recoveryAttemptActive = true
    recoveryAttemptBlocked = false
    recoveryAction = "prepare"
    recoveryFeedback = "Checking recovery safety…"
    recoveryProcessOutput = ""
    recoveryProcessError = ""
    recoveryProc.running = true
  }

  function copyDiagnostics() {
    if (!lightingFailure || recoveryProc.running || recoveryAttemptActive) return
    recoveryAction = "copy-diagnostics"
    recoveryFeedback = "Copying diagnostics…"
    recoveryProcessOutput = ""
    recoveryProcessError = ""
    recoveryProc.running = true
  }

  Component.onCompleted: {
    currentProc.running = true
    tetrisStatusProc.running = true
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
      if (!tetrisStatusProc.running) tetrisStatusProc.running = true
    }
  }

  Process {
    id: tetrisStatusProc
    command: [root.recoveryHelperPath, "status"]
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: root.tetrisProcessOutput = text.trim()
    }
    stderr: StdioCollector {
      waitForEnd: true
      onStreamFinished: root.tetrisProcessError = text.trim()
    }
    onExited: function(exitCode) {
      if (exitCode === 0)
        root.applyTetrisStatus(root.tetrisProcessOutput)
      else {
        root.ramTetrisState = "failed"
        root.ramTetrisMessage = root.tetrisProcessError !== ""
          ? root.tetrisProcessError
          : "Lighting status read failed"
        root.lightingFailure = true
        root.failureScope = "lighting"
        root.failureCode = "LGT-UNK-000"
        root.failureDescription = "Lighting status could not be read."
        root.failureReason = root.ramTetrisMessage
        root.failureReference = "Unavailable"
        root.failureTimestamp = "Unknown"
        root.failureSubsystem = "unknown"
        root.recoveryStatus = "manual-review"
        root.recoverySummary = "Manual review is required."
      }
    }
  }

  Process {
    id: recoveryProc
    command: root.recoveryAction === "recover"
      ? [root.recoveryHelperPath, "recover", "--confirm", root.recoveryToken]
      : root.recoveryAction === "copy-diagnostics"
        ? [root.recoveryHelperPath, "copy-diagnostics"]
        : [root.recoveryHelperPath, "prepare"]
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: root.recoveryProcessOutput = text.trim()
    }
    stderr: StdioCollector {
      waitForEnd: true
      onStreamFinished: root.recoveryProcessError = text.trim()
    }
    onExited: function(exitCode) {
      var action = root.recoveryAction
      if (exitCode !== 0) {
        root.recoveryAttemptActive = false
        if (action !== "copy-diagnostics") root.recoveryAttemptBlocked = true
        root.recoveryToken = ""
        root.recoveryFeedback = root.recoveryProcessError !== ""
          ? root.recoveryProcessError
          : "Recovery check failed."
      } else {
        try {
          var result = JSON.parse(root.recoveryProcessOutput)
          if (action === "prepare") {
            root.recoveryToken = String(result.confirmation_token || "")
            if (root.recoveryToken === "") {
              root.recoveryAttemptActive = false
              root.recoveryAttemptBlocked = true
              root.recoveryFeedback = "Recovery preparation did not bind the incident."
            } else {
              root.recoveryAction = "recover"
              root.recoveryFeedback = "Recovering safely…"
              root.recoveryProcessOutput = ""
              root.recoveryProcessError = ""
              recoveryDispatchTimer.restart()
            }
          } else if (action === "recover") {
            root.recoveryAttemptActive = false
            root.recoveryAttemptBlocked = false
            root.recoveryToken = ""
            root.recoveryFeedback = String(result.message || "Recovery complete.")
            if (!tetrisStatusProc.running) tetrisStatusProc.running = true
          } else {
            root.recoveryFeedback = String(result.message || "Diagnostics copied.")
          }
        } catch (error) {
          root.recoveryAttemptActive = false
          if (action !== "copy-diagnostics") root.recoveryAttemptBlocked = true
          root.recoveryToken = ""
          root.recoveryFeedback = "Recovery response was invalid."
        }
      }
      if (root.recoveryAction === action)
        root.recoveryAction = ""
    }
  }

  Timer {
    id: recoveryDispatchTimer
    interval: 0
    repeat: false
    onTriggered: {
      if (root.recoveryAttemptActive && root.recoveryToken !== ""
          && !recoveryProc.running)
        recoveryProc.running = true
    }
  }

  Process {
    id: tetrisActionProc
    command: [root.tetrisHelperPath, root.tetrisPendingAction]
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: root.tetrisProcessOutput = text.trim()
    }
    stderr: StdioCollector {
      waitForEnd: true
      onStreamFinished: root.tetrisProcessError = text.trim()
    }
    onExited: function(exitCode) {
      if (exitCode !== 0) {
        root.ramTetrisState = "failed"
        root.ramTetrisMessage = root.tetrisProcessError !== ""
          ? root.tetrisProcessError
          : "RAM Tetris toggle failed"
      }
      root.tetrisPendingAction = ""
      if (!tetrisStatusProc.running) tetrisStatusProc.running = true
    }
  }

  Timer {
    interval: 1000
    repeat: true
    running: root.opened
    onTriggered: {
      if (!tetrisStatusProc.running && !tetrisActionProc.running
          && !recoveryProc.running && !root.recoveryAttemptActive)
        tetrisStatusProc.running = true
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
        spacing: Style.space(8)

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
          height: Style.space(80)
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
            anchors.leftMargin: Style.space(14)
            anchors.verticalCenter: parent.verticalCenter
            text: "󱩒"
            color: activeCard.accentColor
            font.family: root.contentFontFamily
            font.pixelSize: Style.space(30)
          }

          Column {
            anchors.left: activeIcon.right
            anchors.leftMargin: Style.space(12)
            anchors.right: activeMeta.left
            anchors.rightMargin: Style.space(12)
            anchors.verticalCenter: parent.verticalCenter
            spacing: Style.space(1)

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
              fontSizeMode: Text.HorizontalFit
              minimumPixelSize: Style.font.body
              font.bold: true
              maximumLineCount: 1
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
            width: Style.space(132)
            anchors.right: parent.right
            anchors.rightMargin: Style.space(12)
            anchors.verticalCenter: parent.verticalCenter
            spacing: Style.space(3)

            Rectangle {
              anchors.horizontalCenter: parent.horizontalCenter
              width: activeKind.implicitWidth + Style.space(18)
              height: Style.space(20)
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

            Text {
              width: parent.width
              text: actionProc.running ? "PRESET TRANSITION" : root.activePresetData.mode
              color: root.contentForeground
              font.family: root.contentFontFamily
              font.pixelSize: Style.font.caption
              font.bold: true
              font.letterSpacing: 0.7
              horizontalAlignment: Text.AlignHCenter
              elide: Text.ElideRight
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
          id: tetrisToggle
          readonly property bool failed: root.lightingFailure
          readonly property color accentColor: failed
            ? "#F7768E"
            : root.ramTetrisPreference ? "#9ECE6A" : "#565F89"
          readonly property string compactRecoveryStatus: root.recoveryAttemptActive
            ? "Recovery in progress"
            : root.recoveryAttemptBlocked || root.recoveryStatus === "blocked"
              ? "Recovery blocked"
              : root.recoveryStatus === "available"
              ? "Recovery needed"
              : "Manual review required"

          width: parent.width
          height: Style.space(failed ? 58 : 46)
          radius: Style.cornerRadius
          color: Qt.rgba(accentColor.r, accentColor.g, accentColor.b, 0.08)
          border.width: 1
          border.color: Qt.rgba(accentColor.r, accentColor.g, accentColor.b, 0.34)

          Text {
            id: tetrisIcon
            anchors.left: parent.left
            anchors.leftMargin: Style.space(12)
            anchors.verticalCenter: parent.verticalCenter
            text: "󰍛"
            color: tetrisToggle.accentColor
            font.family: root.contentFontFamily
            font.pixelSize: Style.space(20)
          }

          Column {
            id: tetrisLabels
            anchors.left: tetrisIcon.right
            anchors.leftMargin: Style.space(8)
            anchors.right: tetrisToggle.failed ? recoveryControls.left : toggleTrack.left
            anchors.rightMargin: Style.space(10)
            anchors.verticalCenter: parent.verticalCenter
            spacing: Style.space(1)

            Text {
              width: parent.width
              text: tetrisToggle.failed && root.failureScope === "lighting"
                ? "Lighting animations stopped"
                : "RAM TETRIS"
              color: root.contentForeground
              font.family: root.contentFontFamily
              font.pixelSize: Style.font.body
              font.bold: true
              font.letterSpacing: 0.9
              elide: Text.ElideRight
            }

            Row {
              width: parent.width
              spacing: Style.space(6)

              Text {
                id: compactErrorCode
                visible: tetrisToggle.failed
                text: root.failureCode
                color: tetrisToggle.accentColor
                font.family: root.contentFontFamily
                font.pixelSize: Style.font.caption
                font.bold: true
                font.letterSpacing: 0.5
              }

              Text {
                width: tetrisToggle.failed
                  ? parent.width - compactErrorCode.implicitWidth - Style.space(6)
                  : parent.width
                text: tetrisToggle.failed
                  ? "· " + tetrisToggle.compactRecoveryStatus
                  : tetrisActionProc.running
                  ? "UPDATING…"
                  : root.ramTetrisPreference ? "Active" : "Static lighting"
                color: tetrisToggle.accentColor
                font.family: root.contentFontFamily
                font.pixelSize: Style.font.caption
                font.letterSpacing: 0.5
                elide: Text.ElideRight
              }
            }
          }

          Rectangle {
            id: toggleTrack
            visible: !tetrisToggle.failed
            width: Style.space(44)
            height: Style.space(24)
            radius: height / 2
            anchors.right: parent.right
            anchors.rightMargin: Style.space(12)
            anchors.verticalCenter: parent.verticalCenter
            color: Qt.rgba(tetrisToggle.accentColor.r, tetrisToggle.accentColor.g, tetrisToggle.accentColor.b, 0.26)
            border.width: 1
            border.color: tetrisToggle.accentColor

            Rectangle {
              width: Style.space(18)
              height: width
              radius: width / 2
              anchors.verticalCenter: parent.verticalCenter
              x: root.ramTetrisPreference
                ? parent.width - width - Style.space(3)
                : Style.space(3)
              color: tetrisToggle.accentColor
            }
          }

          Row {
            id: recoveryControls
            visible: tetrisToggle.failed
            anchors.right: parent.right
            anchors.rightMargin: Style.space(8)
            anchors.verticalCenter: parent.verticalCenter
            spacing: Style.space(5)

            Rectangle {
              id: detailsButton
              width: Style.space(28)
              height: Style.space(28)
              radius: Style.cornerRadius
              color: Qt.rgba(tetrisToggle.accentColor.r, tetrisToggle.accentColor.g, tetrisToggle.accentColor.b, 0.12)
              border.width: 1
              border.color: Qt.rgba(tetrisToggle.accentColor.r, tetrisToggle.accentColor.g, tetrisToggle.accentColor.b, 0.40)

              Text {
                anchors.centerIn: parent
                text: root.diagnosticsExpanded ? "󰅖" : "󰋼"
                color: tetrisToggle.accentColor
                font.family: root.contentFontFamily
                font.pixelSize: Style.font.body
              }

              MouseArea {
                anchors.fill: parent
                cursorShape: Qt.PointingHandCursor
                onClicked: root.diagnosticsExpanded = !root.diagnosticsExpanded
              }
            }

            Rectangle {
              width: Style.space(76)
              height: Style.space(28)
              radius: Style.cornerRadius
              color: Qt.rgba(tetrisToggle.accentColor.r, tetrisToggle.accentColor.g, tetrisToggle.accentColor.b, 0.18)
              border.width: 1
              border.color: tetrisToggle.accentColor
              opacity: root.recoveryAttemptActive ? 0.55 : 1

              Row {
                anchors.centerIn: parent
                spacing: Style.space(4)

                Text {
                  text: "󰑐"
                  color: tetrisToggle.accentColor
                  font.family: root.contentFontFamily
                  font.pixelSize: Style.font.caption
                }

                Text {
                  text: root.recoveryAttemptActive ? "Working" : "Recover"
                  color: tetrisToggle.accentColor
                  font.family: root.contentFontFamily
                  font.pixelSize: Style.font.caption
                  font.bold: true
                }
              }

              MouseArea {
                anchors.fill: parent
                cursorShape: Qt.PointingHandCursor
                enabled: !root.recoveryAttemptActive && !recoveryProc.running
                onClicked: root.beginRecovery()
              }
            }
          }

          MouseArea {
            anchors.fill: parent
            cursorShape: Qt.PointingHandCursor
            enabled: !tetrisToggle.failed && !tetrisActionProc.running
              && !tetrisStatusProc.running
              && !actionProc.running && !currentProc.running
            onClicked: root.toggleRamTetris()
          }
        }

        Rectangle {
          id: diagnosticDetails
          visible: root.lightingFailure && root.diagnosticsExpanded
          width: parent.width
          height: visible ? Style.space(188) : 0
          radius: Style.cornerRadius
          color: Qt.rgba(0.97, 0.46, 0.56, 0.07)
          border.width: visible ? 1 : 0
          border.color: Qt.rgba(0.97, 0.46, 0.56, 0.28)
          clip: true

          Column {
            anchors.fill: parent
            anchors.margins: Style.space(10)
            spacing: Style.space(4)

            Text {
              width: parent.width
              text: root.failureCode + " · " + root.failureDescription
              color: "#F7768E"
              font.family: root.contentFontFamily
              font.pixelSize: Style.font.body
              font.bold: true
              elide: Text.ElideRight
            }

            Text {
              width: parent.width
              text: "Incident " + root.failureReference
                + "  ·  First detected " + root.failureTimestamp
              color: root.contentForeground
              opacity: 0.72
              font.family: root.contentFontFamily
              font.pixelSize: Style.font.caption
              elide: Text.ElideRight
            }

            Text {
              width: parent.width
              text: "Affected: " + root.failureSubsystem
                + "  ·  Recovery: " + root.recoveryStatus
              color: root.contentForeground
              opacity: 0.72
              font.family: root.contentFontFamily
              font.pixelSize: Style.font.caption
              elide: Text.ElideRight
            }

            Flickable {
              width: parent.width
              height: Style.space(72)
              contentWidth: width
              contentHeight: originalReason.implicitHeight
              boundsBehavior: Flickable.StopAtBounds
              clip: true

              Text {
                id: originalReason
                width: parent.width
                text: (root.recoveryFeedback !== ""
                  ? "Latest action: " + root.recoveryFeedback + "\n"
                  : "") + "Original reason: " + root.failureReason
                color: root.contentForeground
                opacity: 0.82
                font.family: root.contentFontFamily
                font.pixelSize: Style.font.caption
                wrapMode: Text.WrapAnywhere
              }
            }

            Row {
              width: parent.width
              spacing: Style.space(8)

              Rectangle {
                width: copyLabel.implicitWidth + Style.space(18)
                height: Style.space(26)
                radius: Style.cornerRadius
                color: Qt.rgba(0.97, 0.46, 0.56, 0.12)
                border.width: 1
                border.color: Qt.rgba(0.97, 0.46, 0.56, 0.36)

                Text {
                  id: copyLabel
                  anchors.centerIn: parent
                  text: "󰆏  Copy diagnostics"
                  color: "#F7768E"
                  font.family: root.contentFontFamily
                  font.pixelSize: Style.font.caption
                  font.bold: true
                }

                MouseArea {
                  anchors.fill: parent
                  cursorShape: Qt.PointingHandCursor
                  enabled: !recoveryProc.running && !root.recoveryAttemptActive
                  onClicked: root.copyDiagnostics()
                }
              }

              Text {
                width: parent.width - copyLabel.implicitWidth - Style.space(26)
                anchors.verticalCenter: parent.verticalCenter
                text: root.recoverySummary
                color: "#F7768E"
                font.family: root.contentFontFamily
                font.pixelSize: Style.font.caption
                elide: Text.ElideRight
              }
            }
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
          columnSpacing: Style.space(8)
          rowSpacing: Style.space(7)
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
              height: Style.space(60)
              radius: Style.cornerRadius
              color: isActive
                ? Qt.rgba(accentColor.r, accentColor.g, accentColor.b, 0.11)
                : mouse.containsMouse || isSelected
                  ? Qt.rgba(root.contentForeground.r, root.contentForeground.g, root.contentForeground.b, 0.11)
                  : Qt.rgba(root.contentForeground.r, root.contentForeground.g, root.contentForeground.b, 0.055)
              border.width: 1
              border.color: isActive
                ? Qt.rgba(accentColor.r, accentColor.g, accentColor.b, 0.62)
                : isSelected
                  ? Qt.rgba(root.contentForeground.r, root.contentForeground.g, root.contentForeground.b, 0.34)
                  : Qt.rgba(root.contentForeground.r, root.contentForeground.g, root.contentForeground.b, 0.10)

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
                anchors.bottom: parent.bottom
                anchors.bottomMargin: Style.space(9)
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
                anchors.bottom: parent.bottom
                anchors.bottomMargin: Style.space(8)
                width: cardKind.implicitWidth + Style.space(12)
                height: Style.space(18)
                radius: Style.cornerRadius
                color: Qt.rgba(presetCard.accentColor.r, presetCard.accentColor.g, presetCard.accentColor.b, 0.10)

                Text {
                  id: cardKind
                  anchors.centerIn: parent
                  text: presetCard.modelData.kind
                  color: presetCard.accentColor
                  font.family: root.contentFontFamily
                  font.pixelSize: Style.font.caption
                  font.bold: true
                  font.letterSpacing: 0.6
                }
              }

              Text {
                anchors.left: parent.left
                anchors.leftMargin: Style.space(12)
                anchors.right: parent.right
                anchors.rightMargin: Style.space(12)
                anchors.top: parent.top
                anchors.topMargin: Style.space(9)
                text: presetCard.modelData.label
                color: root.contentForeground
                font.family: root.contentFontFamily
                font.pixelSize: Style.font.body
                fontSizeMode: Text.HorizontalFit
                minimumPixelSize: Style.font.caption
                font.bold: true
                maximumLineCount: 1
                elide: Text.ElideRight
              }

              MouseArea {
                id: mouse
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                enabled: !actionProc.running && !currentProc.running
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
