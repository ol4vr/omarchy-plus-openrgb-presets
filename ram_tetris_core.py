"""Pure frame generation and scheduling for Corsair DDR5 RAM Tetris.

This is the production-owned form of the experimentally validated offline
prototype.  It deliberately contains no SDK, process, sysfs, or hardware I/O.
"""

from __future__ import annotations

import random
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from fractions import Fraction

LED_COUNT = 12
BLOCK_SIZE = 2
BLOCK_COUNT = LED_COUNT // BLOCK_SIZE
OFF = "#000000"
MAX_FPS = Fraction(5, 1)
GLOBAL_MAX_FPS = Fraction(20, 1)
FRAME_INTERVALS = (Fraction(1, 5), Fraction(3, 10), Fraction(2, 5))

PRESET_PALETTES: Mapping[str, tuple[str, ...]] = {
    "deep-red": ("#8B0000",),
    "deep-blue": ("#000B22",),
    "bright-white": ("#FFFFFF",),
    "animated-rainbow": (
        "#11FF00",
        "#8A2BE2",
        "#FFD400",
        "#FF0040",
    ),
    "neon-rain": ("#5500FF", "#11FF00", "#00FF8C", "#FF00F6", "#FFD400"),
    "aurora-comet": ("#95FF00", "#00D4FF", "#8A2BE2"),
    "spectrum-wave": (
        "#11FF00",
        "#8A2BE2",
        "#FFD400",
        "#FF0040",
    ),
    "electric-sunrise": ("#FF0040", "#FF0051", "#3C00FF", "#0044FF"),
    "matte-black-orange": ("#FF4400", "#E83B00", "#C92B00", "#501000"),
    "black": (),
    "horde-red": ("#8B0000", "#680000", "#4A0000", "#180000"),
    "alliance-blue": ("#0033AA", "#002788", "#001A66", "#000B22"),
}

STATIC_DDR5_COLORS: Mapping[str, str] = {
    "deep-red": "#8B0000",
    "deep-blue": "#000B22",
    "bright-white": "#FFFFFF",
    "animated-rainbow": "#0033AA",
    "neon-rain": "#5500FF",
    "aurora-comet": "#404040",
    "spectrum-wave": "#0033AA",
    "electric-sunrise": "#3C00FF",
    "matte-black-orange": "#501000",
    "black": OFF,
    "horde-red": "#180000",
    "alliance-blue": "#000B22",
}


@dataclass(frozen=True, order=True)
class ControllerIdentity:
    name: str
    location: str


VERIFIED_DIMMS = tuple(
    ControllerIdentity(
        "Corsair Dominator Platinum RGB DDR5",
        "I2C: SMBus I801 adapter at 0000:00:1f.4 "
        f"(/dev/i2c-10), address 0x{address:02X}",
    )
    for address in range(0x18, 0x1C)
)


@dataclass(frozen=True)
class Frame:
    block: int | None
    colors: tuple[str, ...]
    reset: bool = False


def palette_for(preset: str) -> tuple[str, ...]:
    try:
        palette = PRESET_PALETTES[preset]
    except KeyError as error:
        raise ValueError(f"unknown preset: {preset}") from error
    if preset == "black":
        if palette:
            raise ValueError("Black must not define illuminated colors")
        return palette
    if not palette or OFF in palette:
        raise ValueError(f"invalid illuminated palette: {preset}")
    return palette


def generate_cycle(preset: str, seed: int) -> tuple[Frame, ...]:
    """Return the accepted 36 accumulation frames and one reset frame."""

    palette = palette_for(preset)
    if not palette:
        return (Frame(None, (OFF,) * LED_COUNT, True),)
    rng = random.Random(seed)
    if len(palette) == 1:
        block_colors = (palette[0],) * BLOCK_COUNT
    else:
        block_colors = tuple(rng.choice(palette) for _ in range(BLOCK_COUNT))
    landed = [OFF] * LED_COUNT
    frames: list[Frame] = []
    for block, color in enumerate(block_colors):
        landing_start = LED_COUNT - BLOCK_SIZE * (block + 1)
        for falling_start in range(landing_start + 1):
            colors = landed.copy()
            colors[falling_start : falling_start + BLOCK_SIZE] = [color] * BLOCK_SIZE
            frame = Frame(block, tuple(colors))
            if not frames or frame.colors != frames[-1].colors:
                frames.append(frame)
        landed[landing_start : landing_start + BLOCK_SIZE] = [color] * BLOCK_SIZE
    frames.append(Frame(None, (OFF,) * LED_COUNT, True))
    return tuple(frames)


def frame_intervals(seed: int, cycle: int) -> tuple[Fraction, ...]:
    """Return one seeded interval for each block and the reset pause."""

    rng = random.Random((seed << 32) ^ cycle ^ 0x544554524953)
    return tuple(rng.choice(FRAME_INTERVALS) for _ in range(BLOCK_COUNT + 1))


@dataclass
class DimmStream:
    """Independent, indefinitely advancing state for one DIMM."""

    identity: ControllerIdentity
    seed: int
    cycle: int = 0
    frame_index: int = 0
    due: Fraction = Fraction(0)

    def __post_init__(self) -> None:
        self._frames = generate_cycle("horde-red", self.seed)
        self._intervals = frame_intervals(self.seed, self.cycle)

    def reset_for_preset(self, preset: str) -> None:
        self.cycle = 0
        self.frame_index = 0
        self._preset = preset
        self._frames = generate_cycle(preset, self.seed)
        self._intervals = frame_intervals(self.seed, self.cycle)

    @property
    def frame(self) -> Frame:
        return self._frames[self.frame_index]

    def advance(self, written_at: Fraction) -> None:
        frame = self.frame
        interval_index = frame.block if frame.block is not None else BLOCK_COUNT
        self.frame_index += 1
        if self.frame_index == len(self._frames):
            self.cycle += 1
            self.frame_index = 0
            self._frames = generate_cycle(self._preset, self.seed + self.cycle)
            self._intervals = frame_intervals(self.seed, self.cycle)
        self.due = written_at + self._intervals[interval_index]


def default_streams(preset: str, seed: int = 24) -> tuple[DimmStream, ...]:
    """Build four distinct seeds and accepted staggered 40 ms phases."""

    streams = tuple(
        DimmStream(identity, seed + offset, due=Fraction(offset, 25))
        for offset, identity in enumerate(VERIFIED_DIMMS)
    )
    for stream in streams:
        stream.reset_for_preset(preset)
    return streams


def validate_colors(colors: Sequence[str]) -> tuple[str, ...]:
    if len(colors) != LED_COUNT:
        raise ValueError("a DDR5 frame must contain exactly twelve colors")
    return tuple(colors)
