/**
 * Draw Cherie, a pixel poodle puppy, in place of the working row.
 *
 * Special Notes:
 *
 * - Each turn plays the four moves in a fresh random order.
 * - With pixel-cat also loaded, the turn id picks one pet per turn. See pets.ts.
 */

import { atom, read, update } from 'claude-code'
import type { ElementTable, Register, RenderElement } from 'claude-code'

import { CHERIE_FRAMES, CHERIE_HEIGHT, CHERIE_MOVES, CHERIE_WIDTH } from './moves'
import { PET_ALT_PREFIX, hasPet, ownerOf } from './pets'
import type { Pet } from './pets'

const ME: Pet = 'pixel-cherie'
const ALT = `${PET_ALT_PREFIX}Cherie the puppy`

const lastTool = atom({ plugin: 'pixel-cherie', key: 'lastTool' } as const, null)

const FRAME_SECONDS = 0.1

// Each frame is its own pose, so it holds for this many slots to be read.
const HOLD = 3

// Matches the working row height pixel-cat uses.
const SPINNER_HEIGHT_PX = 34

// Without an explicit width the interactive frame takes a default width and pushes the label away.
const SPINNER_WIDTH_PX = Math.round((SPINNER_HEIGHT_PX * CHERIE_WIDTH) / CHERIE_HEIGHT)

function random(): number {
  const [word = 0] = crypto.getRandomValues(new Uint32Array(1))

  return word / 2 ** 32
}

/**
 * Lay the moves out as one loop in random order.
 *
 * Returns:
 *     The frame index shown in each slot of the loop.
 */
function randomSlots(): number[] {
  const shuffled = Object.values(CHERIE_MOVES)
    .map(frames => ({ frames, key: random() }))
    .sort((a, b) => a.key - b.key)

  return shuffled.flatMap(({ frames }) => frames.flatMap(frame => Array<number>(HOLD).fill(frame)))
}

/**
 * Build the looping SVG for one turn.
 *
 * Args:
 *     slots: The frame index shown in each slot of the loop.
 *
 * Returns:
 *     The SVG markup, every frame stacked and shown only during its own slots.
 *
 * Notes:
 *     Each frame lists only the times its opacity changes, which keeps a long loop small.
 */
function buildSvg(slots: number[]): string {
  const total = slots.length

  const groups = CHERIE_FRAMES.map((frame, k) => {
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
      `<g opacity="0">${frame}<animate attributeName="opacity" values="${values.join(';')}" ` +
      `keyTimes="${times.join(';')}" dur="${(total * FRAME_SECONDS).toFixed(1)}s" calcMode="discrete" ` +
      `repeatCount="indefinite"/></g>`
    )
  }).join('')

  return (
    `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${CHERIE_WIDTH} ${CHERIE_HEIGHT}" ` +
    `shape-rendering="crispEdges" stroke-width="1"><g transform="translate(0 .5)">${groups}</g></svg>`
  )
}

// A tool row reads best with the call's own description, as Bash calls carry one.
function describe(tool: string, input: unknown): string {
  const description = (input as { description?: unknown } | undefined)?.description

  return typeof description === 'string' ? description : tool
}

export const register: Register = on => {
  let svg = buildSvg(randomSlots())

  // Before the first turn no pet has been picked, so Cherie draws.
  let owner: Pet = ME

  // Roll once per turn so the order holds steady while the row redraws.
  on('turn.start', ($, e, next) => {
    svg = buildSvg(randomSlots())
    owner = ownerOf(e.turnId)

    return next(e)
  })

  /**
   * Draw Cherie, or on the other pet's turn show that pet when it draws beneath.
   *
   * Args:
   *     below: Runs the plugins beneath and the engine's own drawing.
   *     label: The text drawn beside Cherie.
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

  // A new model response takes the mark back to the working row, so the tool row lets go of Cherie.
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
