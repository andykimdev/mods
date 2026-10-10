/**
 * Draw a pixel cat that runs, jumps and plays in place of the working row.
 *
 * Special Notes:
 *
 * - Each turn plays the moves in a fresh random order, with a run between each two.
 * - About one turn in four the cat gets a random color scheme for that whole turn.
 * - With pixel-cherie also loaded, the turn id picks one pet per turn. See pets.ts.
 * - /pet cat, /pet cherie or /pet random sets which pet draws for the rest of the session.
 */

import { atom, read, update } from 'claude-code'
import type { ElementTable, Register, RenderElement } from 'claude-code'

import { CAT_FRAMES, CAT_HEIGHT, CAT_MOVES, CAT_PALETTE, CAT_WIDTH } from './moves'
import { PET_ALT_PREFIX, PET_COMMAND, hasPet, parseChoice, petReply, pick } from './pets'
import type { Choice, Pet } from './pets'

const ME: Pet = 'pixel-cat'
const ALT = `${PET_ALT_PREFIX}Pixel cat running`

const lastTool = atom({ plugin: 'pixel-cat', key: 'lastTool' } as const, null)

const FRAME_SECONDS = 0.1
const RECOLOR_CHANCE = 0.25

// Slow moves hold each frame for this many slots so the Zs and the heart can be read.
const HOLD: Record<string, number> = { sleep: 3, heart: 2 }

// The working row draws its cat at about this height, so the tool rows match it.
const SPINNER_HEIGHT_PX = 34

// Without an explicit width the interactive frame takes a default width and pushes the label away.
const SPINNER_WIDTH_PX = Math.round((SPINNER_HEIGHT_PX * CAT_WIDTH) / CAT_HEIGHT)

function random(): number {
  const [word = 0] = crypto.getRandomValues(new Uint32Array(1))

  return word / 2 ** 32
}

function hsl(hue: number, saturation: number, lightness: number): string {
  const s = saturation / 100
  const l = lightness / 100
  const a = s * Math.min(l, 1 - l)
  const channel = (n: number) => {
    const k = (n + hue / 30) % 12
    const value = l - a * Math.max(-1, Math.min(k - 3, 9 - k, 1))

    return Math.round(value * 255).toString(16).padStart(2, '0')
  }

  return `#${channel(0)}${channel(8)}${channel(4)}`
}

/**
 * Pick a random scheme that keeps the dark outline and the light to dark order of the coat.
 *
 * Returns:
 *     Six colors in the same order as CAT_PALETTE.
 */
function randomPalette(): string[] {
  const hue = random() * 360
  const saturation = 45 + random() * 40

  return [
    CAT_PALETTE[0],
    hsl(hue, saturation, 28),
    hsl(hue, saturation, 46),
    hsl(hue, saturation, 56),
    hsl((hue + 30) % 360, 60, 86),
    hsl((hue + 180) % 360, 80, 58),
  ]
}

/**
 * Lay the moves out as one loop: a run, then each other move in random order, each followed by a run.
 *
 * Returns:
 *     The frame index shown in each slot of the loop.
 */
function randomSlots(): number[] {
  const run = CAT_MOVES.run ?? []
  const extras = Object.entries(CAT_MOVES)
    .filter(([name]) => name !== 'run')
    .map(([name, frames]) => ({ name, frames, key: random() }))
    .sort((a, b) => a.key - b.key)

  return extras.flatMap(({ name, frames }) => [
    ...run,
    ...frames.flatMap(frame => Array<number>(HOLD[name] ?? 1).fill(frame)),
  ])
}

/**
 * Build the looping SVG for one turn.
 *
 * Args:
 *     palette: Six colors in the same order as CAT_PALETTE.
 *     slots: The frame index shown in each slot of the loop.
 *
 * Returns:
 *     The SVG markup, every frame stacked and shown only during its own slots.
 *
 * Notes:
 *     Each frame lists only the times its opacity changes, which keeps a long loop small.
 */
function buildSvg(palette: readonly string[], slots: number[]): string {
  const swap = (body: string) =>
    CAT_PALETTE.reduce((out, color, i) => out.split(`"${color}"`).join(`"${palette[i]}"`), body)
  const total = slots.length

  const groups = CAT_FRAMES.map((frame, k) => {
    if (!slots.includes(k)) {
      return ''
    }

    const values: string[] = []
    const times: string[] = []

    slots.forEach((slot, t) => {
      const shown = slot === k ? '1' : '0'

      if (values[values.length - 1] !== shown) {
        values.push(shown)
        times.push(t === 0 ? '0' : (t / total).toFixed(5))
      }
    })

    if (times[0] !== '0') {
      values.unshift('0')
      times.unshift('0')
    }

    return (
      `<g opacity="0">${swap(frame)}<animate attributeName="opacity" values="${values.join(';')}" ` +
      `keyTimes="${times.join(';')}" dur="${(total * FRAME_SECONDS).toFixed(1)}s" calcMode="discrete" ` +
      `repeatCount="indefinite"/></g>`
    )
  }).join('')

  return (
    `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${CAT_WIDTH} ${CAT_HEIGHT}" ` +
    `shape-rendering="crispEdges" stroke-width="1"><g transform="translate(0 .5)">${groups}</g></svg>`
  )
}

// A tool row reads best with the call's own description, as Bash calls carry one.
function describe(tool: string, input: unknown): string {
  const description = (input as { description?: unknown } | undefined)?.description

  return typeof description === 'string' ? description : tool
}

export const register: Register = on => {
  let svg = buildSvg(CAT_PALETTE, randomSlots())

  // Before the first turn no pet has been picked, so the cat draws.
  let owner: Pet = ME

  // What /pet set for this session.
  let choice: Choice = 'random'

  on('session.start', async ($, e, next) => {
    await $.command.register(PET_COMMAND)

    return next(e)
  })

  on('command.run', { command: 'pet' }, async ($, e, next) => {
    const parsed = parseChoice(e.args)

    if (parsed !== undefined) {
      choice = parsed

      // A fixed pet takes the row at once rather than at the next turn.
      if (parsed !== 'random') {
        owner = parsed
      }
    }

    // The other pet's hook sits beneath and has to hear the choice too.
    await next(e)

    return { text: petReply(e.args, choice) }
  })

  // Roll once per turn so the order and colors hold steady while the row redraws.
  on('turn.start', ($, e, next) => {
    svg = buildSvg(random() < RECOLOR_CHANCE ? randomPalette() : CAT_PALETTE, randomSlots())
    owner = pick(choice, e.turnId)

    return next(e)
  })

  /**
   * Draw the cat, or on the other pet's turn show that pet when it draws beneath.
   *
   * Args:
   *     below: Runs the plugins beneath and the engine's own drawing.
   *     label: The text drawn beside the cat.
   *     table: The desktop's elements.
   *
   * Returns:
   *     The tree to draw.
   */
  async function drawOrYield(
    below: () => Promise<RenderElement>,
    label: string,
    table: ElementTable<'desktop'>,
  ): Promise<RenderElement> {
    if (owner !== ME) {
      const tree = await below()

      if (hasPet(tree)) {
        return tree
      }
    }

    const { Box, Svg, Text } = table

    return (
      <Box alignItems="center">
        <Svg source={svg} alt={ALT} width={SPINNER_WIDTH_PX} height={SPINNER_HEIGHT_PX} isInteractive />
        <Text dimColor> {label}</Text>
      </Box>
    )
  }

  on('tool.call', async ($, e, next) => {
    await update($, lastTool, () => e.tool_use_id)

    return next(e)
  }).catch(($, e, next) => next(e)) // A failed write must never block the tool call itself.

  // A new model response takes the mark back to the working row, so the tool row lets go of the cat.
  on('turn.step', async function* ($, e, next) {
    await update($, lastTool, () => null)

    return yield* next(e)
  })

  on('turn.complete', async ($, e, next) => {
    await update($, lastTool, () => null)

    return next(e)
  })

  // The desktop draws the turn's mark on the latest tool row, while it runs and until the next response.
  // Any other row gets the engine's own drawing with its result and expand control.
  on('ui.render', { component: 'ToolUse' }, async ($, e, next) => {
    if (e.surface !== 'desktop') {
      return next(e)
    }

    const isLatest = e.requestId === (await read($, lastTool))

    if (!e.props.isRunning && !isLatest) {
      return next(e)
    }

    return drawOrYield(() => next(e), describe(e.props.tool, e.props.input), $.ui.resolve(e))
  })

  // Reads, searches and edits fold into one group line, which carries the mark while it is live.
  on('ui.render', { component: 'ToolGroup' }, ($, e, next) => {
    const latest = e.props.calls[e.props.calls.length - 1]

    if (e.surface !== 'desktop' || !e.props.isActive || e.props.isExpanded || !latest) {
      return next(e)
    }

    return drawOrYield(() => next(e), describe(latest.tool, latest.input), $.ui.resolve(e))
  })

  on('ui.render', { component: 'Spinner' }, ($, e, next) => {
    // Only the desktop can draw an Svg.
    if (e.surface !== 'desktop') {
      return next(e)
    }

    return drawOrYield(() => next(e), `${e.props.message ?? e.props.word}${e.props.suffix}`, $.ui.resolve(e))
  })
}
