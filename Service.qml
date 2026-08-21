import QtQuick
import Quickshell
import Quickshell.Io

Item {
  id: root

  readonly property string helperPath: Quickshell.env("HOME")
    + "/.config/omarchy/plugins/io.github.ol4vr.openrgb-presets/apply-preset"
  property string restoreOutput: ""
  property string restoreError: ""

  Process {
    id: serverProc
    command: [
      "/usr/bin/openrgb",
      "--noautoconnect",
      "--startminimized",
      "--server",
      "--server-host", "127.0.0.1",
      "--server-port", "6742"
    ]
    running: false

    // Keep one GUI-capable OpenRGB host alive so the Effects Plugin and SDK
    // remain ready after the one-time hardware scan. Consume its output so
    // the process pipes cannot fill.
    stdout: SplitParser {
      onRead: function() {}
    }
    stderr: SplitParser {
      onRead: function() {}
    }
  }

  Process {
    id: restoreProc
    command: [root.helperPath, "--restore"]
    running: false

    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: root.restoreOutput = text.trim()
    }
    stderr: StdioCollector {
      waitForEnd: true
      onStreamFinished: root.restoreError = text.trim()
    }
    onExited: function(exitCode) {
      if (exitCode === 0) {
        console.info("OpenRGB preset restored: " + root.restoreOutput)
      } else if (exitCode === 75) {
        console.info("OpenRGB preset restore skipped because another operation is active")
      } else {
        console.error("OpenRGB preset restore failed: "
          + (root.restoreError !== "" ? root.restoreError : "exit " + exitCode))
      }
    }
  }

  Component.onCompleted: {
    serverProc.running = true
    restoreProc.running = true
  }
  Component.onDestruction: serverProc.running = false
}
