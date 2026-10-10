/**
 * Decide which pixel pet draws during a turn, so pixel-cat and pixel-cherie take turns when both load.
 *
 * Special Notes:
 *
 * - pixel-cat and pixel-cherie each keep an identical copy of this file. Change both together.
 * - Both mods hash the same turn id, so they agree on the owner without talking to each other.
 */

// Every pet that shares the working row, in one fixed order both mods agree on.
export const PETS = ['pixel-cat', 'pixel-cherie'] as const

export type Pet = (typeof PETS)[number]

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
