import QtQuick
import Quickshell
import Quickshell.Io

Item {
  id: root

  readonly property string lifecyclePath: Quickshell.env("HOME")
    + "/.config/omarchy/plugins/io.github.ol4vr.openrgb-presets/openrgb-lifecycle"
  property bool shuttingDown: false

  Process {
    id: lifecycleProc
    command: [root.lifecyclePath]
    running: false

    stdout: SplitParser {
      onRead: function(line) {
        console.info("OpenRGB lifecycle: " + line)
      }
    }
    stderr: SplitParser {
      onRead: function(line) {
        console.warn("OpenRGB lifecycle: " + line)
      }
    }
    onExited: function(exitCode) {
      if (!root.shuttingDown) {
        console.error("OpenRGB lifecycle exited with code " + exitCode
          + "; restarting in two seconds")
        restartTimer.start()
      }
    }
  }

  Timer {
    id: restartTimer
    interval: 2000
    repeat: false
    onTriggered: {
      if (!root.shuttingDown && !lifecycleProc.running) {
        lifecycleProc.running = true
      }
    }
  }

  Component.onCompleted: lifecycleProc.running = true
  Component.onDestruction: {
    root.shuttingDown = true
    restartTimer.stop()
    lifecycleProc.running = false
  }
}
