# pixel-cat

A Claude Code mod that replaces the orange working dots with an animated pixel cat. The cat runs, jumps, pounces, turns around, naps, sends a heart, wags its tail, tilts its head and play bows, in a new random order every turn. About one turn in four it also gets a random color scheme.

## Where the cat shows

- **Working row:** While Claude thinks or writes a reply.
- **Tool rows:** While a tool runs, on that tool's row.

The desktop app still draws its own dots in the step header while a tool runs. Mods cannot change that header.

## Sharing turns with pixel-cherie

With [pixel-cherie](../pixel-cherie) also loaded, each turn shows either the cat or Cherie, about half the turns each. Either mod works alone.

## Requirements

- macOS or Linux.
- A recent Claude Code with mod support. This mod was built on version 2.1.293.
- The cat draws in the desktop app Code tab. The terminal keeps its usual spinner.

## Install

1. Clone the mods repo into `~/.claude/mods`, or unzip, so the folder sits at `~/.claude/mods/pixel-cat` with `.claude-plugin`, `hooks` and `types` directly inside it.
2. Open `~/.claude/settings.json`. Create it with `{}` if it does not exist.
3. Add the absolute path of the folder to `CLAUDE_CODE_PLUGIN_DIRS` inside the `env` block. Separate several folders with colons, and keep any folders already listed.
4. Run `claude plugin validate ~/.claude/mods/pixel-cat` and check that it ends with Validation passed.
5. Restart Claude Code. Sessions that were already open do not load new mods.

Example `env` block with no other mods:

```json
{
  "env": {
    "CLAUDE_CODE_PLUGIN_DIRS": "/Users/yourname/.claude/mods/pixel-cat"
  }
}
```

## Uninstall

1. Remove the pixel-cat path from `CLAUDE_CODE_PLUGIN_DIRS`.
2. Delete `~/.claude/mods/pixel-cat`.
3. Restart Claude Code.

## Files

- **`hooks/register.tsx`:** Draws the cat and picks the move order and colors each turn.
- **`hooks/moves.ts`:** Holds the 44 animation frames and the frames each move plays.
- **`hooks/pets.ts`:** Picks the cat or Cherie for each turn when [pixel-cherie](../pixel-cherie) is also loaded.
- **`types/index.d.ts`:** Declares the one value the mod keeps for the session.
- **`frames/loop.svg`:** A preview of every move in one loop. Open it in a browser.
