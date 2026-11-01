# OpenRGB Presets — Static Edition

Hugin's twelve reviewed OpenRGB presets, with all four Corsair DDR5 DIMMs kept
in static Direct mode. RAM is written only during startup restoration, an
explicit preset change, or an explicit RAM Lighting ON/OFF action. There is no
RAM animation process, scheduler, background writer, Tetris mode, or lighting
recovery engine.

## Presets

The names, non-RAM behavior, Effects profiles, controller zones, and colors are
unchanged from the accepted v0.4.8 static-DDR5 implementation:

- Deep Red
- Deep Blue
- Bright White
- Animated Rainbow
- Neon Rain
- Aurora Comet
- Spectrum Wave
- Electric Sunrise
- Matte Black Orange
- Black (Turn Off RGB)
- Horde Red
- Alliance Blue

The exact reviewed 12-LED static DDR5 patterns from v0.4.45 are retained,
including the multicolor Rainbow, Rain, Comet, Sunrise, Horde, and Alliance
patterns. Effects profiles never contain a DDR5 assignment. Electric Sunrise's
static red, violet, and blue pattern is the default when no saved selection
exists.

## RAM Lighting master switch

RAM Lighting ON applies the selected preset's one static DDR5 color. OFF sends
static black to the shared four-DIMM controller and changes no GPU, ST100,
motherboard, or Effects state. The preference is stored as `on` or `off` in:

```text
~/.local/state/omarchy-plus/openrgb-presets/ram-lighting-enabled
```

Missing preference state defaults to ON. Static black is an RGB value, not a
promise that electrical LED power is removed.

## Safety contract

Every startup restoration and explicit mutation is serialized by one
`apply.flock`. Before any Effects or OpenRGB write, `apply-preset` requires:

- `openrgb-hugin 1.0rc3-3.2`;
- executable SHA-256
  `d0d065994b7328aec2cc0ae2b06a3c9ab8f99f4693aba35bd669e2fea406e301`;
- one loopback listener owned by the exact accepted OpenRGB server command,
  executable, and user;
- exactly seven accepted controllers: four Corsair DDR5 DIMMs plus the GPU,
  ST100, and motherboard;
- one readable, plausible temperature from each SPD5118 endpoint `10-0050`
  through `10-0053`; and
- a ready OpenRGB Effects Plugin.

OpenRGB CLI calls always use `--nodetect`. The retained Hugin configuration
disables only `ASUS Aura SMBus Motherboard`; the USB/HID motherboard detector
remains enabled. A failed identity, inventory, SPD, Effects, timeout, or command
check stops without persisting a new selection or RAM preference.

## Lifecycle

`omarchy-plus-openrgb-presets.service` owns one OpenRGB SDK child. It restores
the selected preset once after authenticated startup, stops its exact child for
sleep, and restores only non-RAM preset state after resume. It never writes RAM
on resume. An unexpected SDK exit fails the service without automatic restart.
The lifecycle does not poll RAM health or write lighting while idle.

The plugin itself is only a bar widget. The reviewed user unit is installed and
enabled separately by the BASE reconciliation through
`reconcile-static-service install`; enabling does not start it in the current
session. The reconciler contains no start, stop, restart, or `--now` operation.

Historical v0.4.45 failure latches, lifecycle boundaries, journals, and bundles
are archives. Static Edition neither reads, clears, migrates, nor interprets
them.

## Validation

```bash
omarchy plugin validate "$PWD"
qmllint -I "$OMARCHY_PATH/shell" BarWidget.qml Panel.qml
bash -n apply-preset openrgb-lifecycle install-effects-plugin reconcile-static-service
python3 -c 'compile(open("effects-sdk", encoding="utf-8").read(), "effects-sdk", "exec")'
python3 tests/test-presets.py
python3 tests/test-static-lifecycle.py
./apply-preset --list
./apply-preset --dry-run electric-sunrise
./apply-preset --dry-run --ram-off
./apply-preset --dry-run --ram-on
```

Dry runs print commands and never contact OpenRGB or write preference state.
Live acceptance is intentionally excluded from source review.

See `MIGRATION.md` for the stopped-service migration and rollback procedure.
