"""
Build a pixel pet's frame module and preview SVGs from a folder of square pixel SVG frames.

Purpose:

- Read each frame, remove the white background at the edge, and crop all frames to one box.
- Merge the closest colors until every move fits one desktop Svg, then write the mod files.

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

# The longest Svg source the desktop draws, and generous room for each frame's tags and the outer svg.
SVG_SOURCE_LIMIT = 131_072
FRAME_OVERHEAD = 400
SVG_OVERHEAD = 400

PATH = re.compile(r'<path fill="(#[0-9a-fA-F]{6})" d="([^"]*)"\s*/>')

# One filled rectangle: a move, a width, a height, then back to the start, with either separator.
RECT = re.compile(r"M(\d+)[ ,](\d+)h(\d+)v(\d+)(?:H\d+|h-\d+)z")

Grid = list[list[str | None]]


def read_frame(path: Path) -> Grid:
    """
    Read one SVG frame into a grid of colors.

    Args:
        path: An SVG whose paths fill whole cells with rectangles, one path per rectangle or
            many rectangles in one path, on an optional white background rect.

    Returns:
        A row-major grid of lowercase hex colors, None where nothing is drawn.

    Raises:
        ValueError: When the SVG holds a shape this reader does not understand.
    """
    text = path.read_text()
    box = re.search(r'viewBox="0 0 (\d+) (\d+)"', text)

    if box is None:
        raise ValueError(f"{path}: no viewBox")

    width, height = int(box.group(1)), int(box.group(2))
    paths = PATH.findall(text)

    if len(paths) != text.count("<path") or re.search(r"<(?!\?xml|!--|svg|/svg|g|/g|path|rect)", text):
        raise ValueError(f"{path}: holds shapes other than filled paths")

    grid: Grid = [[None] * width for _ in range(height)]

    for color, d in paths:
        rects = RECT.findall(d)

        if "".join(RECT.sub("", d).split()):
            raise ValueError(f"{path}: a {color} path is not made of cell rectangles")

        for x, y, w, h in rects:
            for row in range(int(y), int(y) + int(h)):
                for col in range(int(x), int(x) + int(w)):
                    grid[row][col] = color.lower()

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


def fit(grids: list[Grid], moves: list[list[int]]) -> tuple[list[Grid], list[str], list[tuple[str, str]]]:
    """
    Merge the closest pair of colors, one pair at a time, until every move fits one Svg.

    Args:
        grids: Frames as grids of hex colors.
        moves: The frame indices of each move. register.tsx packs moves into Svgs per turn.

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
        sizes = [len(encode(g, palette)) + FRAME_OVERHEAD for g in grids]
        total = max(sum(sizes[k] for k in move) + SVG_OVERHEAD for move in moves)

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

    starts = [sum(m["frames"] for m in moves[:i]) for i in range(len(moves))]
    indices = {m["name"]: list(range(s, s + m["frames"])) for m, s in zip(moves, starts)}
    grids, palette, merges = fit(crop([remove_background(read_frame(p)) for p in paths]), list(indices.values()))
    height, width = len(grids[0]), len(grids[0][0])
    frames = [encode(g, palette) for g in grids]
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
    size = max(sum(len(frames[k]) + FRAME_OVERHEAD for k in ks) + SVG_OVERHEAD for ks in indices.values())
    merged = ", ".join(f"{a} into {b}" for a, b in merges) or "none"

    return (f"{len(frames)} frames, {width} x {height}, {len(palette)} colors, "
            f"largest move about {size} characters, merged {merged}")


if __name__ == "__main__":
    mod_folder = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(__file__).resolve().parent.parent
    print(build(Path(sys.argv[1]), mod_folder))
