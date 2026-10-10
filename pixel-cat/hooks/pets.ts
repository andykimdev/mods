/**
 * Decide which pixel pet draws during a turn, so pet mods take turns when several load.
 *
 * Special Notes:
 *
 * - Every pet mod keeps an identical copy of this file, written by the pet-new skill.
 * - Each mod hashes the same turn id, so they agree on the owner without talking to each other.
 * - Each mod registers /pet and passes each run on, so all of them hear the same choice.
 */

// Every pet, in one fixed order all copies agree on: its mod, the word /pet takes, and its name.
export const PETS = [
  { mod: 'pixel-cat', word: 'cat', name: 'the cat' },
  { mod: 'pixel-cherie', word: 'cherie', name: 'Cherie' },
] as const

export type Pet = (typeof PETS)[number]['mod']

// What /pet sets for the session: one pet every turn, or a pick per turn.
export type Choice = Pet | 'random'

// Each pet starts its Svg alt with this, so a pet can tell another pet's tree from the engine's own.
export const PET_ALT_PREFIX = 'Pixel pet: '

const WORDS = [...PETS.map(p => p.word), 'random']

export const PET_COMMAND = {
  name: 'pet',
  description: `Choose which pixel pet draws: ${listed(WORDS)}`,
  argumentHint: WORDS.join(' | '),
  immediate: true,
} as const

// Join words as a list a reader says aloud: a, b or c.
function listed(words: readonly string[]): string {
  return words.length < 2 ? words.join('') : `${words.slice(0, -1).join(', ')} or ${words[words.length - 1]}`
}

/**
 * Pick the pet that owns a turn.
 *
 * Args:
 *     turnId: The id every hook of the turn carries.
 *
 * Returns:
 *     The pet that draws during that turn.
 */
export function ownerOf(turnId: string): Pet {
  // FNV-1a spreads similar ids across the pets.
  let hash = 2166136261

  for (let i = 0; i < turnId.length; i++) {
    hash = Math.imul(hash ^ turnId.charCodeAt(i), 16777619) >>> 0
  }

  return (PETS[hash % PETS.length] ?? PETS[0]).mod
}

/**
 * Pick the pet that draws during a turn under a /pet choice.
 *
 * Args:
 *     choice: The choice /pet set, random when none was set.
 *     turnId: The id every hook of the turn carries.
 *
 * Returns:
 *     The chosen pet, or the turn id's pet when the choice is random.
 */
export function pick(choice: Choice, turnId: string): Pet {
  return choice === 'random' ? ownerOf(turnId) : choice
}

/**
 * Read the word typed after /pet.
 *
 * Args:
 *     args: Everything typed after the command name.
 *
 * Returns:
 *     The choice the word names, or undefined for an empty or unknown word.
 */
export function parseChoice(args: string): Choice | undefined {
  const word = args.trim().toLowerCase()

  return word === 'random' ? 'random' : PETS.find(p => p.word === word)?.mod
}

/**
 * Write the reply /pet prints.
 *
 * Args:
 *     args: Everything typed after the command name.
 *     choice: The choice in force after the run.
 *
 * Returns:
 *     A confirmation, or the usage line and current choice when the word is empty or unknown.
 */
export function petReply(args: string, choice: Choice): string {
  const label =
    choice === 'random'
      ? `${listed(PETS.map(p => p.name))}, picked each turn`
      : `${PETS.find(p => p.mod === choice)?.name ?? choice} every turn`

  if (parseChoice(args) === undefined) {
    return `Usage: ${listed(WORDS.map(w => `/pet ${w}`))}. Now showing ${label}.`
  }

  return `Now showing ${label}.`
}

/**
 * Report whether a drawn tree holds a pixel pet.
 *
 * Args:
 *     node: A tree or string a ui.render hook returned.
 *
 * Returns:
 *     True when any Svg in the tree has an alt that starts with PET_ALT_PREFIX.
 */
export function hasPet(node: unknown): boolean {
  if (typeof node !== 'object' || node === null) {
    return false
  }

  const element = node as { type?: unknown; props?: { alt?: unknown }; children?: unknown }

  if (element.type === 'Svg') {
    return typeof element.props?.alt === 'string' && element.props.alt.startsWith(PET_ALT_PREFIX)
  }

  return Array.isArray(element.children) && element.children.some(hasPet)
}
