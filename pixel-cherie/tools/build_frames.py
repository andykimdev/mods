"""
Build the pixel-cherie frame module and preview SVGs from a folder of 72 x 72 pixel SVG frames.

Purpose:

- Read each frame, merge near-identical shades, and remove the white background at the edge.
- Write hooks/moves.ts, one SVG per frame, and a loop.svg preview of every move.

Special Notes:

- Run as python3 tools/build_frames.py <svg folder> from the pixel-cherie folder.
- Frames are read in file name order, and each move takes the next five.
- Fails when all frames together would pass the desktop limit for one Svg source.
"""

import json
import re
import sys
from pathlib import Path

MOVES = ["play", "sit", "rest", "bunny"]
FRAMES_PER_MOVE = 5

# Three peach shades a viewer cannot tell apart at row height cost about 18,000 characters.
MERGE = {"#fec89b": "#fec293", "#f9c399": "#fec293"}

# A cell this close to white and touching the frame edge is background.
WHITE_MIN_SUM = 3 * 235

# Matches register.tsx, so the preview plays at the same speed.
HOLD = 3
FRAME_SECONDS = 0.1

# The longest Svg source the desktop draws, less room for each frame's animate tag.
SVG_SOURCE_LIMIT = 131_072
FRAME_OVERHEAD = 400

RUN = re.compile(r'<path fill="(#[0-9a-f]{6})" d="M(\d+) (\d+)h(\d+)v1H\d+z"/>')

Grid = list[list[str | None]]


def read_frame(path: Path) -> Grid:
    """
    Read one SVG frame into a grid of colors.

    Args:
        path: An SVG whose paths each fill one horizontal run of cells.

    Returns:
        A row-major grid of hex colors, None where nothing is drawn.

    Raises:
        ValueError: When the SVG holds a path this reader does not understand.
    """
    text = path.read_text()
    size = int(re.search(r'viewBox="0 0 (\d+) \d+"', text).group(1))
    runs = RUN.findall(text)

    if len(runs) != text.count("<path"):
        raise ValueError(f"{path}: {text.count('<path') - len(runs)} paths are not one-row runs")

    grid: Grid = [[None] * size for _ in range(size)]

    for color, x, y, width in runs:
        for i in range(int(width)):
            grid[int(y)][int(x) + i] = MERGE.get(color, color)

    return grid


def remove_background(grid: Grid) -> Grid:
    """
    Clear the near-white cells connected to the frame edge.

    Args:
        grid: A row-major grid of hex colors.

    Returns:
        A copy with those cells set to None. White inside the drawing, such as eye shine, stays.
    """
    size = len(grid)

    def whiteish(c: str | None) -> bool:
        return c is None or sum(int(c[i:i + 2], 16) for i in (1, 3, 5)) >= WHITE_MIN_SUM

    out = [row[:] for row in grid]
    stack = [(x, y) for y in range(size) for x in range(size) if x in (0, size - 1) or y in (0, size - 1)]
    seen = set()

    while stack:
        x, y = stack.pop()

        if (x, y) in seen or not (0 <= x < size and 0 <= y < size) or not whiteish(grid[y][x]):
            continue

        seen.add((x, y))
        out[y][x] = None
        stack += [(x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)]

    return out


def crop(grids: list[Grid]) -> list[Grid]:
    """
    Crop every frame to the smallest box that holds all of them, so the frames stay aligned.

    Args:
        grids: Frames of the same size.

    Returns:
        The cropped frames.
    """
    cells = [(x, y) for g in grids for y, row in enumerate(g) for x, c in enumerate(row) if c]
    x0, x1 = min(x for x, _ in cells), max(x for x, _ in cells)
    y0, y1 = min(y for _, y in cells), max(y for _, y in cells)

    return [[row[x0:x1 + 1] for row in g[y0:y1 + 1]] for g in grids]


def encode(grid: Grid, palette: list[str]) -> str:
    """
    Encode a frame as one stroked path per color, the format pixel-cat uses.

    Args:
        grid: A row-major grid of hex colors.
        palette: Every color, in the order the paths are written.

    Returns:
        SVG path elements for the frame.
    """
    paths = []

    for color in palette:
        parts: list[str] = []
        cx = cy = None

        for y, row in enumerate(grid):
            x = 0

            while x < len(row):
                if row[x] != color:
                    x += 1
                    continue

                start = x

                while x < len(row) and row[x] == color:
                    x += 1

                parts.append(f"M{start} {y}" if cx is None else f"m{start - cx} {y - cy}")
                parts.append(f"h{x - start}")
                cx, cy = x, y

        if parts:
            paths.append(f'<path stroke="{color}" d="{"".join(parts).replace(" -", "-")}"/>')

    return "".join(paths)


def svg(width: int, height: int, body: str, scale: int) -> str:
    """Wrap frame paths in an SVG element drawn at scale pixels per cell."""
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width * scale}" height="{height * scale}" '
        f'viewBox="0 0 {width} {height}" shape-rendering="crispEdges" stroke-width="1">'
        f'<g transform="translate(0 .5)">{body}</g></svg>'
    )


def loop(frames: list[str], slots: list[int]) -> str:
    """
    Stack every frame and show each only during its own slots, as register.tsx does.

    Args:
        frames: Path elements of each frame.
        slots: The frame index shown in each slot of the loop.

    Returns:
        The frame groups with their animate tags.
    """
    total = len(slots)
    groups = []

    for k, frame in enumerate(frames):
        values: list[str] = []
        times: list[str] = []

        for t, slot in enumerate(slots):
            shown = "1" if slot == k else "0"

            if not values or values[-1] != shown:
                values.append(shown)
                times.append("0" if t == 0 else f"{t / total:.5f}")

        if times[0] != "0":
            values.insert(0, "0")
            times.insert(0, "0")

        groups.append(
            f'<g opacity="0">{frame}<animate attributeName="opacity" values="{";".join(values)}" '
            f'keyTimes="{";".join(times)}" dur="{total * FRAME_SECONDS:.1f}s" calcMode="discrete" '
            f'repeatCount="indefinite"/></g>'
        )

    return "".join(groups)


def main(source: Path, mod: Path) -> None:
    paths = sorted(source.glob("*.svg"))

    if len(paths) != len(MOVES) * FRAMES_PER_MOVE:
        raise ValueError(f"{source}: found {len(paths)} SVGs, expected {len(MOVES) * FRAMES_PER_MOVE}")

    grids = crop([remove_background(read_frame(p)) for p in paths])
    height, width = len(grids[0]), len(grids[0][0])
    used = {c for g in grids for row in g for c in row if c}
    palette = sorted(used, key=lambda c: sum(int(c[i:i + 2], 16) for i in (1, 3, 5)))
    frames = [encode(g, palette) for g in grids]
    total = sum(len(f) + FRAME_OVERHEAD for f in frames)

    if total >= SVG_SOURCE_LIMIT:
        raise ValueError(f"frames need about {total} characters, over the {SVG_SOURCE_LIMIT} limit")

    moves = {name: list(range(i * FRAMES_PER_MOVE, (i + 1) * FRAMES_PER_MOVE)) for i, name in enumerate(MOVES)}
    rows = "".join(f"  '{f}',\n" for f in frames)
    (mod / "hooks/moves.ts").write_text(
        "/**\n * The pixel-cherie moves, as SVG frames and the order each move plays them.\n *\n"
        " * Special Notes:\n *\n * - Written by tools/build_frames.py. Rebuild rather than edit.\n */\n\n"
        f"export const CHERIE_WIDTH = {width}\nexport const CHERIE_HEIGHT = {height}\n\n"
        "// Distinct frames, each one stroked path per color, drawn on rows offset by half a pixel.\n"
        f"export const CHERIE_FRAMES = [\n{rows}]\n\n"
        "// Each move is the list of frames it shows, one per slot.\n"
        f"export const CHERIE_MOVES: Record<string, number[]> = {json.dumps(moves)}\n"
    )

    out = mod / "frames"
    out.mkdir(exist_ok=True)

    for name, indices in moves.items():
        for i, k in enumerate(indices):
            (out / f"{name}_{i:02d}.svg").write_text(svg(width, height, frames[k], 10))

    slots = [k for name in MOVES for k in moves[name] for _ in range(HOLD)]
    (out / "loop.svg").write_text(svg(width, height, loop(frames, slots), 5))
    print(f"{len(frames)} frames, {width} x {height}, {len(palette)} colors, about {total} characters")


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(__file__).resolve().parent.parent)
