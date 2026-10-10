# pixel-cherie

A Claude Code mod that replaces the orange working dots with Cherie, a pixel poodle puppy. Cherie plays, sits, rests and cuddles a toy bunny, in a new random order every turn.

## Where Cherie shows

- **Working row:** While Claude thinks or writes a reply.
- **Tool rows:** While a tool runs, on that tool's row.

The desktop app still draws its own dots in the step header while a tool runs. Mods cannot change that header.

## Sharing turns with pixel-cat

With [pixel-cat](../pixel-cat) also loaded, each turn shows either Cherie or the cat, about half the turns each. Either mod works alone.

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

Example `env` block with both pets:

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

## Files

- **`hooks/register.tsx`:** Draws Cherie and picks the move order each turn.
- **`hooks/moves.ts`:** Holds the 20 animation frames and the frames each move plays. Written by `tools/build_frames.py`.
- **`hooks/pets.ts`:** Picks Cherie or the cat for each turn. pixel-cat keeps an identical copy.
- **`types/index.d.ts`:** Declares the one value the mod keeps for the session.
- **`tests/pets.test.ts`:** Checks the turn picker and that all frames fit one drawing. Run `claude plugin test ~/.claude/mods/pixel-cherie`.
- **`frames/loop.svg`:** A preview of every move in one loop. Open it in a browser.
- **`tools/build_frames.py`:** Rebuilds `hooks/moves.ts` and `frames/` from a folder of 20 SVG frames. Run `python3 tools/build_frames.py <folder>` from this folder.
