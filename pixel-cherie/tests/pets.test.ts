/**
 * Test how pixel-cherie shares turns with other pets, the /pet choice, and that each frame fits one Svg.
 *
 * Special Notes:
 *
 * - Written by the pet-new skill. Every pet mod keeps the same tests apart from the frames import.
 */

import { describe, expect, test } from 'claude-code/testing'

import { CHERIE_FRAMES, CHERIE_MOVES } from '../hooks/moves'
import { PETS, PET_ALT_PREFIX, hasPet, ownerOf, parseChoice, petReply, pick } from '../hooks/pets'

// The longest Svg source the desktop draws.
const SVG_SOURCE_LIMIT = 131_072

// Generous room for each frame's group and animate tag, plus the outer svg element.
const FRAME_OVERHEAD = 400
const SVG_OVERHEAD = 400

const MODS = PETS.map(p => p.mod)
const first = PETS[0]
const petSvg = { type: 'Svg', props: { source: '<svg/>', alt: `${PET_ALT_PREFIX}Cherie` } }
const otherSvg = { type: 'Svg', props: { source: '<svg/>', alt: 'Loading' } }
const row = (...children: unknown[]) => ({ type: 'Box', children })

describe('ownerOf', () => {
  test('returns the same pet for the same turn id', async () => {
    expect(ownerOf('turn-42')).toBe(ownerOf('turn-42'))
  })

  test('gives every pet some of 300 turn ids', async () => {
    const owners = new Set(Array.from({ length: 300 }, (_, i) => ownerOf(`turn-${i}`)))

    expect([...owners].sort()).toEqual([...MODS].sort())
  })

  test('picks a pet for an empty turn id', async () => {
    expect(MODS).toContain(ownerOf(''))
  })
})

describe('pick', () => {
  test('returns the chosen pet whatever the turn id', async () => {
    expect([pick('pixel-cherie', 'turn-1'), pick('pixel-cherie', 'turn-2')]).toEqual(['pixel-cherie', 'pixel-cherie'])
  })

  test('falls back to the turn id pick for random', async () => {
    expect(pick('random', 'turn-42')).toBe(ownerOf('turn-42'))
  })
})

describe('parseChoice', () => {
  test('reads every pet word and random in any case and spacing', async () => {
    const words = [...PETS.map(p => ` ${p.word.toUpperCase()} `), 'Random']

    expect(words.map(parseChoice)).toEqual([...MODS, 'random'])
  })

  test('rejects an empty, unknown or doubled word', async () => {
    expect(['', 'dragon', `${first.word} ${first.word}`].map(parseChoice)).toEqual([undefined, undefined, undefined])
  })
})

describe('petReply', () => {
  test('confirms a valid choice', async () => {
    expect(petReply(first.word, first.mod)).toBe(`Now showing ${first.name} every turn.`)
  })

  test('names every pet in the usage line for an unknown word', async () => {
    const reply = petReply('dragon', first.mod)

    expect([...PETS.map(p => reply.includes(`/pet ${p.word}`)), reply.endsWith(`Now showing ${first.name} every turn.`)])
      .toEqual([...PETS.map(() => true), true])
  })
})

describe('hasPet', () => {
  test('finds a pet Svg nested in a row', async () => {
    expect(hasPet(row(row(petSvg), 'Working'))).toBe(true)
  })

  test('ignores an Svg without the pet alt', async () => {
    expect(hasPet(row(otherSvg, 'Working'))).toBe(false)
  })

  test('ignores a plain string and an empty row', async () => {
    expect([hasPet('Working'), hasPet(row())]).toEqual([false, false])
  })
})

test('every frame of every move fits one Svg source', async () => {
  const frames = Object.values(CHERIE_MOVES).flat()
  const sizes = frames.map(k => (CHERIE_FRAMES[k]?.length ?? SVG_SOURCE_LIMIT) + FRAME_OVERHEAD + SVG_OVERHEAD)

  expect(sizes.filter(size => size >= SVG_SOURCE_LIMIT)).toEqual([])
})
