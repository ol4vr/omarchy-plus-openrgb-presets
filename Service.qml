import QtQuick
import Quickshell.Io

Item {
  id: root

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

  Component.onCompleted: serverProc.running = true
  Component.onDestruction: serverProc.running = false
}
