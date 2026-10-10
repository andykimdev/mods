/**
 * Decide which pixel pet draws during a turn, so pixel-cat and pixel-cherie take turns when both load.
 *
 * Special Notes:
 *
 * - pixel-cat and pixel-cherie each keep an identical copy of this file. Change both together.
 * - Both mods hash the same turn id, so they agree on the owner without talking to each other.
 * - Both mods register /pet and pass each run on, so both hear the same choice.
 */

// Every pet that shares the working row, in one fixed order both mods agree on.
export const PETS = ['pixel-cat', 'pixel-cherie'] as const

export type Pet = (typeof PETS)[number]

// What /pet sets for the session: one pet every turn, or a pick per turn.
export type Choice = Pet | 'random'

// The word typed after /pet for each choice, and how the reply names it.
const CHOICES: Record<string, { choice: Choice; label: string }> = {
  cat: { choice: 'pixel-cat', label: 'the cat every turn' },
  cherie: { choice: 'pixel-cherie', label: 'Cherie every turn' },
  random: { choice: 'random', label: 'the cat or Cherie, picked each turn' },
}

export const PET_COMMAND = {
  name: 'pet',
  description: 'Choose which pixel pet draws: cat, cherie or random',
  argumentHint: 'cat | cherie | random',
  immediate: true,
} as const

// Each pet starts its Svg alt with this, so a pet can tell another pet's tree from the engine's own.
export const PET_ALT_PREFIX = 'Pixel pet: '

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
  // FNV-1a spreads similar ids across both pets.
  let hash = 2166136261

  for (let i = 0; i < turnId.length; i++) {
    hash = Math.imul(hash ^ turnId.charCodeAt(i), 16777619) >>> 0
  }

  return PETS[hash % PETS.length] ?? PETS[0]
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
  return CHOICES[args.trim().toLowerCase()]?.choice
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
  const label = Object.values(CHOICES).find(c => c.choice === choice)?.label ?? choice

  if (parseChoice(args) === undefined) {
    return `Usage: /pet cat, /pet cherie or /pet random. Now showing ${label}.`
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
