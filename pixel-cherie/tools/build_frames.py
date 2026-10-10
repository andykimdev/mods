"""
Build a pixel pet's frame module and preview SVGs from a folder of square pixel SVG frames.

Purpose:

- Read each frame, remove the white background at the edge, and crop all frames to one box.
- Merge the closest colors until every frame fits one desktop Svg, then write the mod files.

Special Notes:

- Run as python3 build_frames.py <svg folder> [mod folder]. The mod folder defaults to the
  parent of this script's folder, so a copy in <mod>/tools runs with the folder alone.
- The moves come from <mod>/pet.json, each taking the next frames in file name order.
"""

import json
import re
import sys
from pathlib import Path

# A cell this close to white and touching the frame edge is background.
WHITE_MIN_SUM = 3 * 235

# Matches register.tsx, so the preview plays at the same speed.
HOLD = 3
FRAME_SECONDS = 0.1

# The longest Svg source the desktop draws, less room for each frame's animate tag.
SVG_SOURCE_LIMIT = 131_072
FRAME_OVERHEAD = 400

RUN = re.compile(r'<path fill="(#[0-9a-fA-F]{6})" d="M(\d+) (\d+)h(\d+)v1H\d+z"/>')

Grid = list[list[str | None]]


def read_frame(path: Path) -> Grid:
    """
    Read one SVG frame into a grid of colors.

    Args:
        path: An SVG whose paths each fill one horizontal run of cells.

    Returns:
        A row-major grid of lowercase hex colors, None where nothing is drawn.

    Raises:
        ValueError: When the SVG holds a path this reader does not understand.
    """
    text = path.read_text()
    box = re.search(r'viewBox="0 0 (\d+) (\d+)"', text)

    if box is None:
        raise ValueError(f"{path}: no viewBox")

    width, height = int(box.group(1)), int(box.group(2))
    runs = RUN.findall(text)

    if len(runs) != text.count("<path"):
        raise ValueError(f"{path}: {text.count('<path') - len(runs)} paths are not one-row runs")

    grid: Grid = [[None] * width for _ in range(height)]

    for color, x, y, run in runs:
        for i in range(int(run)):
            grid[int(y)][int(x) + i] = color.lower()

    return grid


def brightness(color: str) -> int:
    """Return the sum of a hex color's channels."""
    return sum(int(color[i:i + 2], 16) for i in (1, 3, 5))


def remove_background(grid: Grid) -> Grid:
    """
    Clear the near-white cells connected to the frame edge.

    Args:
        grid: A row-major grid of hex colors.

    Returns:
        A copy with those cells set to None. White inside the drawing, such as eye shine, stays.
    """
    height, width = len(grid), len(grid[0])
    out = [row[:] for row in grid]
    stack = [(x, y) for y in range(height) for x in range(width)
             if x in (0, width - 1) or y in (0, height - 1)]
    seen = set()

    while stack:
        x, y = stack.pop()

        if (x, y) in seen or not (0 <= x < width and 0 <= y < height):
            continue

        seen.add((x, y))
        color = grid[y][x]

        if color is not None and brightness(color) < WHITE_MIN_SUM:
            continue

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

    Raises:
        ValueError: When every frame is empty.
    """
    cells = [(x, y) for g in grids for y, row in enumerate(g) for x, c in enumerate(row) if c]

    if not cells:
        raise ValueError("every frame is empty after removing the background")

    x0, x1 = min(x for x, _ in cells), max(x for x, _ in cells)
    y0, y1 = min(y for _, y in cells), max(y for _, y in cells)

    return [[row[x0:x1 + 1] for row in g[y0:y1 + 1]] for g in grids]


def encode(grid: Grid, palette: list[str]) -> str:
    """
    Encode a frame as one stroked path per color.

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


def fit(grids: list[Grid]) -> tuple[list[Grid], list[str], list[tuple[str, str]]]:
    """
    Merge the closest pair of colors, one pair at a time, until all frames fit one Svg.

    Args:
        grids: Frames as grids of hex colors.

    Returns:
        The frames after merging, the palette darkest first, and each merge as (from, into).

    Raises:
        ValueError: When the frames do not fit even with one color.

    Notes:
        The less used color of a pair is replaced by the more used one, so large areas keep
        their color.
    """
    merges: list[tuple[str, str]] = []

    while True:
        counts: dict[str, int] = {}

        for g in grids:
            for row in g:
                for c in row:
                    if c:
                        counts[c] = counts.get(c, 0) + 1

        palette = sorted(counts, key=brightness)
        total = sum(len(encode(g, palette)) + FRAME_OVERHEAD for g in grids)

        if total < SVG_SOURCE_LIMIT:
            return grids, palette, merges

        if len(palette) < 2:
            raise ValueError(f"frames need about {total} characters even with one color")

        def distance(pair: tuple[str, str]) -> int:
            a, b = pair
            return sum((int(a[i:i + 2], 16) - int(b[i:i + 2], 16)) ** 2 for i in (1, 3, 5))

        pairs = [(a, b) for i, a in enumerate(palette) for b in palette[i + 1:]]
        a, b = min(pairs, key=lambda p: (distance(p), p))
        old, new = (a, b) if counts[a] < counts[b] else (b, a)
        merges.append((old, new))
        grids = [[[new if c == old else c for c in row] for row in g] for g in grids]


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


def build(source: Path, mod: Path) -> str:
    """
    Write hooks/moves.ts, one SVG per frame and frames/loop.svg for the pet in mod.

    Args:
        source: A folder of SVG frames, read in file name order.
        mod: The pet's mod folder, holding pet.json.

    Returns:
        A one-line summary of the build.

    Raises:
        ValueError: When the frame count does not match the moves in pet.json.
    """
    spec = json.loads((mod / "pet.json").read_text())
    moves = spec["moves"]
    prefix = spec["word"].upper()
    paths = sorted(source.glob("*.svg"))
    wanted = sum(m["frames"] for m in moves)

    if len(paths) != wanted:
        raise ValueError(f"{source}: found {len(paths)} SVGs, pet.json moves take {wanted}")

    grids, palette, merges = fit(crop([remove_background(read_frame(p)) for p in paths]))
    height, width = len(grids[0]), len(grids[0][0])
    frames = [encode(g, palette) for g in grids]
    starts = [sum(m["frames"] for m in moves[:i]) for i in range(len(moves))]
    indices = {m["name"]: list(range(s, s + m["frames"])) for m, s in zip(moves, starts)}
    rows = "".join(f"  '{f}',\n" for f in frames)

    (mod / "hooks").mkdir(exist_ok=True)
    (mod / "hooks/moves.ts").write_text(
        f"/**\n * The {mod.name} moves, as SVG frames and the order each move plays them.\n *\n"
        " * Special Notes:\n *\n * - Written by tools/build_frames.py. Rebuild rather than edit.\n */\n\n"
        f"export const {prefix}_WIDTH = {width}\nexport const {prefix}_HEIGHT = {height}\n\n"
        "// Distinct frames, each one stroked path per color, drawn on rows offset by half a pixel.\n"
        f"export const {prefix}_FRAMES = [\n{rows}]\n\n"
        "// Each move is the list of frames it shows, one per slot.\n"
        f"export const {prefix}_MOVES: Record<string, number[]> = {json.dumps(indices)}\n"
    )

    out = mod / "frames"
    out.mkdir(exist_ok=True)

    for old in out.glob("*.svg"):
        old.unlink()

    for name, ks in indices.items():
        for i, k in enumerate(ks):
            (out / f"{name}_{i:02d}.svg").write_text(svg(width, height, frames[k], 10))

    slots = [k for ks in indices.values() for k in ks for _ in range(HOLD)]
    (out / "loop.svg").write_text(svg(width, height, loop(frames, slots), 5))
    size = sum(len(f) + FRAME_OVERHEAD for f in frames)
    merged = ", ".join(f"{a} into {b}" for a, b in merges) or "none"

    return f"{len(frames)} frames, {width} x {height}, {len(palette)} colors, about {size} characters, merged {merged}"


if __name__ == "__main__":
    mod_folder = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(__file__).resolve().parent.parent
    print(build(Path(sys.argv[1]), mod_folder))
