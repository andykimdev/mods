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

# Colors this close to white count as near-white. A near-white patch this small that touches
# the background is edge fringe from tracing, while larger patches are white fur.
WHITE_MIN_SUM = 3 * 235
FRINGE_MAX_CELLS = 3
WHITE = "#ffffff"

# An enclosed blank pocket ringed mostly by dark outline is background showing between limbs,
# while white fur is ringed mostly by light fur. Measured on pixel-kitty: background pockets
# ran 0.74 to 0.80 dark and fur pockets at most 0.38. A smaller pocket in a dark ring is eye
# shine, while the background pockets there held 36 cells or more.
DARK_MAX_SUM = 300
DARK_BORDER_SHARE = 0.6
DARK_POCKET_MIN_CELLS = 10

# The engine does not read a module file over 1,048,576 bytes, so frames go in files under this.
CHUNK_BYTES = 900_000

# Matches register.tsx, so the preview plays at the same speed. pet.json frame_seconds sets
# how many slots each frame holds.
FRAME_SECONDS = 0.1
DEFAULT_FRAME_SECONDS = 0.3

# The longest Svg source the desktop draws, and generous room for each frame's tags and the outer svg.
SVG_SOURCE_LIMIT = 131_072
FRAME_OVERHEAD = 400
SVG_OVERHEAD = 400

PATH = re.compile(r'<path fill="(#[0-9a-fA-F]{6})" d="([^"]*)"\s*/>')

# One filled cell rectangle drawn as its own rect element.
RECT_TAG = re.compile(r'<rect x="(\d+)" y="(\d+)" width="(\d+)" height="(\d+)" fill="(#[0-9a-fA-F]{6})"\s*/>')

# One filled rectangle: a move, a width, a height, then back to the start, with either separator.
RECT = re.compile(r"M(\d+)[ ,](\d+)h(\d+)v(\d+)(?:H\d+|h-\d+)z")

Grid = list[list[str | None]]


def read_frame(path: Path) -> Grid:
    """
    Read one SVG frame into a grid of colors.

    Args:
        path: An SVG whose paths or rect elements fill whole cells with rectangles, one path
            per rectangle or many rectangles in one path.

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
    tags = RECT_TAG.findall(text)

    if len(paths) != text.count("<path") or len(tags) != text.count("<rect") or re.search(r"<(?!\?xml|!--|svg|/svg|g|/g|path|rect)", text):
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

    for x, y, w, h, color in tags:
        for row in range(int(y), int(y) + int(h)):
            for col in range(int(x), int(x) + int(w)):
                grid[row][col] = color.lower()

    return grid


def brightness(color: str) -> int:
    """Return the sum of a hex color's channels."""
    return sum(int(color[i:i + 2], 16) for i in (1, 3, 5))


def flood(cells: set[tuple[int, int]], starts: list[tuple[int, int]]) -> set[tuple[int, int]]:
    """Return the cells of a set reachable from the starts through four-way neighbors."""
    seen: set[tuple[int, int]] = set()
    stack = [s for s in starts if s in cells]

    while stack:
        x, y = stack.pop()

        if (x, y) in seen:
            continue

        seen.add((x, y))
        stack += [n for n in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)) if n in cells and n not in seen]

    return seen


def remove_background(grid: Grid) -> Grid:
    """
    Clear the background around the drawing and the tiny near-white fringe that touches it.

    Args:
        grid: A row-major grid of hex colors, None where nothing is drawn.

    Returns:
        A copy where the background is None. Undrawn or pure white cells the background does
        not reach become white, since the white page showed through them as white fur.

    Notes:
        Undrawn and pure white cells are blank. The background spreads from the frame edge
        only through blank cells with no drawn neighbor, so it cannot pass a gap of one or
        two cells in the outline. It then takes the blank cells beside it, any thin blank
        pocket that opens onto it, and any large enclosed pocket ringed mostly by dark outline.
    """
    height, width = len(grid), len(grid[0])
    cells = [(x, y) for y in range(height) for x in range(width)]
    blank = {(x, y) for x, y in cells if grid[y][x] in (None, WHITE)}

    def around(x: int, y: int) -> list[tuple[int, int]]:
        return [(x + dx, y + dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1) if dx or dy]

    def inside(c: tuple[int, int]) -> bool:
        return 0 <= c[0] < width and 0 <= c[1] < height

    core = {c for c in blank if all(n in blank or not inside(n) for n in around(*c))}
    seeds = [c for c in blank if c[0] in (0, width - 1) or c[1] in (0, height - 1)]
    reached = flood(core | set(seeds), seeds)
    background = reached | {n for c in reached for n in around(*c) if n in blank}

    rest = blank - background

    while rest:
        pocket = flood(rest, [next(iter(rest))])
        rest -= pocket
        opens = any(n in background for x, y in pocket for n in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)))

        border = [grid[y + dy][x + dx] for x, y in pocket for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))
                  if inside((x + dx, y + dy)) and (x + dx, y + dy) not in blank]
        dark = sum(1 for c in border if c and brightness(c) < DARK_MAX_SUM)

        ringed = len(pocket) >= DARK_POCKET_MIN_CELLS and border and dark / len(border) >= DARK_BORDER_SHARE

        if (opens and not pocket & core) or ringed:
            background |= pocket

    out: Grid = [[None if (x, y) in background else (grid[y][x] or WHITE) for x in range(width)]
                 for y in range(height)]
    pale = {(x, y) for x, y in cells if out[y][x] and brightness(out[y][x]) >= WHITE_MIN_SUM}

    while pale:
        patch = flood(pale, [next(iter(pale))])
        pale -= patch
        touches = any(n in background for x, y in patch for n in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)))

        if touches and len(patch) <= FRINGE_MAX_CELLS:
            for x, y in patch:
                out[y][x] = None

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
    Merge the closest pair of colors, one pair at a time, until every frame fits one Svg.

    Args:
        grids: Frames as grids of hex colors.
        moves: The frame indices of each move. register.tsx packs frames into Svgs per turn.

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
        total = max(sizes[k] + SVG_OVERHEAD for move in moves for k in move)

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


def chunks(frames: list[str]) -> list[list[str]]:
    """
    Split frames into consecutive groups whose module files stay under CHUNK_BYTES.

    Args:
        frames: Path elements of each frame.

    Returns:
        The groups, in order, never empty.
    """
    groups: list[list[str]] = [[]]
    size = 0

    for frame in frames:
        cost = len(frame.encode()) + 6

        if groups[-1] and size + cost > CHUNK_BYTES:
            groups.append([])
            size = 0

        groups[-1].append(frame)
        size += cost

    return groups


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
    hooks = mod / "hooks"
    hooks.mkdir(exist_ok=True)

    for old in hooks.glob("frames_*.ts"):
        old.unlink()

    groups = chunks(frames)
    note = " *\n * Special Notes:\n *\n * - Written by tools/build_frames.py. Rebuild rather than edit.\n */\n\n"

    for i, group in enumerate(groups):
        rows = "".join(f"  '{f}',\n" for f in group)
        (hooks / f"frames_{i}.ts").write_text(
            f"/**\n * Frames of {mod.name}, part {i + 1} of {len(groups)}, each one stroked path per color.\n"
            f"{note}export const FRAMES_{i} = [\n{rows}]\n"
        )

    imports = "".join(f"import {{ FRAMES_{i} }} from './frames_{i}'\n" for i in range(len(groups)))
    spread = ", ".join(f"...FRAMES_{i}" for i in range(len(groups)))
    (hooks / "moves.ts").write_text(
        f"/**\n * The {mod.name} moves, as SVG frames and the order each move plays them.\n{note}"
        f"{imports}\nexport const {prefix}_WIDTH = {width}\nexport const {prefix}_HEIGHT = {height}\n\n"
        "// Distinct frames, drawn on rows offset by half a pixel, split across files the engine can read.\n"
        f"export const {prefix}_FRAMES = [{spread}]\n\n"
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

    hold = max(1, round(spec.get("frame_seconds", DEFAULT_FRAME_SECONDS) / FRAME_SECONDS))
    slots = [k for ks in indices.values() for k in ks for _ in range(hold)]
    (out / "loop.svg").write_text(svg(width, height, loop(frames, slots), 5))
    size = max(len(f) for f in frames) + FRAME_OVERHEAD + SVG_OVERHEAD
    pages = -(-sum(len(f) + FRAME_OVERHEAD for f in frames) // (SVG_SOURCE_LIMIT - SVG_OVERHEAD))
    merged = ", ".join(f"{a} into {b}" for a, b in merges) or "none"

    return (f"{len(frames)} frames, {width} x {height}, {len(palette)} colors, largest frame about "
            f"{size} characters, about {pages} Svg pages per cycle, merged {merged}")


if __name__ == "__main__":
    mod_folder = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(__file__).resolve().parent.parent
    print(build(Path(sys.argv[1]), mod_folder))
