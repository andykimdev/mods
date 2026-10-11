# pixel-cherie

A Claude Code mod that replaces the orange working dots with Cherie, a pixel poodle puppy. Cherie plays, sits, rests and cuddles a toy bunny, in a new random order every turn.

<p align="center">
  <img src="assets/in-app.png" width="193" alt="Cherie on the Working row in the desktop app">
</p>

## Where Cherie shows

- **Working row:** While Claude thinks or writes a reply.
- **Tool rows:** While a tool runs, on that tool's row.

The desktop app still draws its own dots in the step header while a tool runs. Mods cannot change that header.

## Choosing a pet

With [pixel-cat](../pixel-cat) also loaded, each turn shows one of the loaded pets. Each mod works alone.

To choose for the rest of the session, type one of these in the desktop app:

- **`/pet cat`:** Shows the cat every turn.
- **`/pet cherie`:** Shows Cherie every turn.
- **`/pet random`:** Picks a pet each turn. This is the default.

## Requirements

- macOS or Linux.
- A recent Claude Code with mod support. This mod was built on version 2.1.293.
- Cherie draws in the desktop app Code tab. The terminal keeps its usual spinner.

## Install

1. Clone the mods repo into `~/.claude/mods`, or unzip, so the folder sits at `~/.claude/mods/pixel-cherie` with `.claude-plugin`, `hooks` and `types` directly inside it.
2. Open `~/.claude/settings.json`. Create it with `{}` if it does not exist.
3. Add the absolute path of the folder to `CLAUDE_CODE_PLUGIN_DIRS` inside the `env` block. Separate several folders with colons, and keep any folders already listed.
4. Run `claude plugin validate ~/.claude/mods/pixel-cherie` and check that it ends with Validation passed.
5. Restart Claude Code. Sessions that were already open do not load new mods.

Example `env` block with every pet:

```json
{
  "env": {
    "CLAUDE_CODE_PLUGIN_DIRS": "/Users/yourname/.claude/mods/pixel-cat:/Users/yourname/.claude/mods/pixel-cherie"
  }
}
```

## Uninstall

1. Remove the pixel-cherie path from `CLAUDE_CODE_PLUGIN_DIRS`.
2. Delete `~/.claude/mods/pixel-cherie`.
3. Restart Claude Code.

## Development

- **Tests:** Run `claude plugin test ~/.claude/mods/pixel-cherie`. Checks the turn picker, `/pet` and the frame size.
- **Frames:** Run `python3 tools/build_frames.py <folder>` from `~/.claude/mods/pixel-cherie`. Rebuilds `hooks/moves.ts` and `frames/` from a folder of SVG frames.

## Files

- **`pet.json`:** Describes the pet for the generated files.
- **`hooks/register.tsx`:** Draws Cherie and picks the move order each turn.
- **`hooks/moves.ts`:** Holds the 240 animation frames and the frames each move plays.
- **`hooks/frames_*.ts`:** Holds the frame data in parts, each small enough for the engine to read.
- **`hooks/pets.ts`:** Picks the pet for each turn and reads `/pet`. Every pet mod keeps an identical copy.
- **`types/index.d.ts`:** Declares the one value the mod keeps for the session.
- **`tests/pets.test.ts`:** Checks the turn picker, `/pet` and the frame size.
- **`tools/build_frames.py`:** Rebuilds `hooks/moves.ts` and `frames/` from a folder of SVG frames.
- **`frames/loop.svg`:** Previews every move in one loop. Open it in a browser.
- **`assets/in-app.png`:** Shows Cherie in the desktop app.
