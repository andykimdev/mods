/**
 * Draw Cherie, a pixel poodle puppy, in place of the working row.
 *
 * Special Notes:
 *
 * - Each turn plays the moves in a fresh random order.
 * - Frames that do not all fit one Svg are split into pages, and a timer swaps the page when it ends.
 * - With other pet mods loaded, the turn id picks one pet per turn. See pets.ts.
 * - /pet sets which pet draws for the rest of the session.
 */

import { atom, read, update } from 'claude-code'
import type { ElementTable, EngineInterface, Register, RenderElement, Timer } from 'claude-code'

import { CHERIE_FRAMES, CHERIE_HEIGHT, CHERIE_MOVES, CHERIE_WIDTH } from './moves'
import { PET_ALT_PREFIX, PET_COMMAND, hasPet, parseChoice, petReply, pick } from './pets'
import type { Choice, Pet } from './pets'

const ME: Pet = 'pixel-cherie'
const ALT = `${PET_ALT_PREFIX}Cherie`

const lastTool = atom({ plugin: 'pixel-cherie', key: 'lastTool' } as const, null)

const FRAME_SECONDS = 0.1

// Each frame holds for this many slots, from frame_seconds in pet.json.
const HOLD = 2

// The longest Svg source the desktop draws, and generous room for each frame's tags and the outer svg.
const SVG_SOURCE_LIMIT = 131_072
const FRAME_OVERHEAD = 400
const SVG_OVERHEAD = 400

// Matches the working row height every pet uses.
const SPINNER_HEIGHT_PX = 34

// Without an explicit width the interactive frame takes a default width and pushes the label away.
const SPINNER_WIDTH_PX = Math.round((SPINNER_HEIGHT_PX * CHERIE_WIDTH) / CHERIE_HEIGHT)

function random(): number {
  const [word = 0] = crypto.getRandomValues(new Uint32Array(1))

  return word / 2 ** 32
}

/**
 * Shuffle the moves and pack their frames, in that order, into pages that each fit one Svg.
 *
 * Returns:
 *     Each page as the frame index shown in each of its slots.
 *
 * Notes:
 *     A pet whose frames all fit one Svg gets a single page, so nothing swaps. A long move
 *     carries on across pages, so it plays through without a break.
 */
function randomPages(): number[][] {
  const order = Object.values(CHERIE_MOVES)
    .map(frames => ({ frames, key: random() }))
    .sort((a, b) => a.key - b.key)
    .flatMap(({ frames }) => frames)
  const pages: number[][] = []
  let page: number[] = []
  let drawn = new Set<number>()
  let size = SVG_OVERHEAD

  for (const frame of order) {
    const cost = (CHERIE_FRAMES[frame]?.length ?? 0) + FRAME_OVERHEAD

    // A frame already on the page costs nothing more, since each frame is drawn once per Svg.
    if (!drawn.has(frame) && page.length > 0 && size + cost >= SVG_SOURCE_LIMIT) {
      pages.push(page)
      page = []
      drawn = new Set<number>()
      size = SVG_OVERHEAD
    }

    if (!drawn.has(frame)) {
      size += cost
      drawn.add(frame)
    }

    page.push(...Array<number>(HOLD).fill(frame))
  }

  return [...pages, page]
}

/**
 * Build every page of one turn.
 *
 * Returns:
 *     Each page's SVG and how long it plays, in milliseconds.
 */
function buildPages(): { svg: string; ms: number }[] {
  return randomPages().map(slots => ({ svg: buildSvg(slots), ms: slots.length * FRAME_SECONDS * 1000 }))
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

// The pages of the running turn, the one on show, and the timer that swaps to the next.
type Pages = { list: { svg: string; ms: number }[]; index: number; swap: Timer | undefined }

/**
 * Swap to the next page once the current one has played through, and redraw with it.
 *
 * Args:
 *     $: The engine interface of the hook that started the turn.
 *     pages: The turn's pages, updated in place.
 */
function schedule($: EngineInterface, pages: Pages): void {
  pages.swap?.cancel()
  pages.swap = undefined

  const current = pages.list[pages.index]

  if (pages.list.length < 2 || current === undefined) {
    return
  }

  pages.swap = $.clock.after(current.ms, () => {
    pages.index = (pages.index + 1) % pages.list.length
    $.ui.invalidate('ui.render')
    schedule($, pages)
  })
}

// A tool row reads best with the call's own description, as Bash calls carry one.
function describe(tool: string, input: unknown): string {
  const description = (input as { description?: unknown } | undefined)?.description

  return typeof description === 'string' ? description : tool
}

export const register: Register = on => {
  const pages: Pages = { list: buildPages(), index: 0, swap: undefined }

  // Before the first turn no pet has been picked, so Cherie draws.
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

  // Roll once per turn so the order holds steady while the row redraws.
  on('turn.start', ($, e, next) => {
    pages.list = buildPages()
    pages.index = 0
    schedule($, pages)
    owner = pick(choice, e.turnId)

    return next(e)
  })

  /**
   * Draw Cherie, or on another pet's turn show that pet when it draws beneath.
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
        <Svg source={pages.list[pages.index]?.svg ?? ''} alt={ALT} width={SPINNER_WIDTH_PX} height={SPINNER_HEIGHT_PX} isInteractive />
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
    // Nothing draws once the turn ends, so the swaps stop until the next one.
    pages.swap?.cancel()
    pages.swap = undefined
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
