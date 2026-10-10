/**
 * Test how pixel-cat shares turns with pixel-cherie, the /pet choice, and that its frames fit one Svg.
 */

import { describe, expect, test } from 'claude-code/testing'

import { CAT_FRAMES } from '../hooks/moves'
import { PET_ALT_PREFIX, hasPet, ownerOf, parseChoice, petReply, pick } from '../hooks/pets'

// The longest Svg source the desktop draws.
const SVG_SOURCE_LIMIT = 131_072

// Generous room for each frame's group and animate tag, plus the outer svg element.
const FRAME_OVERHEAD = 400
const SVG_OVERHEAD = 400

const petSvg = { type: 'Svg', props: { source: '<svg/>', alt: `${PET_ALT_PREFIX}Cherie the puppy` } }
const otherSvg = { type: 'Svg', props: { source: '<svg/>', alt: 'Loading' } }
const row = (...children: unknown[]) => ({ type: 'Box', children })

describe('ownerOf', () => {
  test('returns the same pet for the same turn id', async () => {
    expect(ownerOf('turn-42')).toBe(ownerOf('turn-42'))
  })

  test('gives each pet some of 200 turn ids', async () => {
    const owners = new Set(Array.from({ length: 200 }, (_, i) => ownerOf(`turn-${i}`)))

    expect([...owners].sort()).toEqual(['pixel-cat', 'pixel-cherie'])
  })

  test('picks a pet for an empty turn id', async () => {
    expect(['pixel-cat', 'pixel-cherie']).toContain(ownerOf(''))
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
  test('reads each word in any case and spacing', async () => {
    expect(['cat', ' Cherie ', 'RANDOM'].map(parseChoice)).toEqual(['pixel-cat', 'pixel-cherie', 'random'])
  })

  test('rejects an empty, unknown or doubled word', async () => {
    expect(['', 'dog', 'cat cherie'].map(parseChoice)).toEqual([undefined, undefined, undefined])
  })
})

describe('petReply', () => {
  test('confirms a valid choice', async () => {
    expect(petReply('cherie', 'pixel-cherie')).toBe('Now showing Cherie every turn.')
  })

  test('shows usage and the current choice for an unknown word', async () => {
    expect(petReply('dog', 'random')).toBe(
      'Usage: /pet cat, /pet cherie or /pet random. Now showing the cat or Cherie, picked each turn.',
    )
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

test('every frame together fits one Svg source', async () => {
  const total = CAT_FRAMES.reduce((sum, frame) => sum + frame.length + FRAME_OVERHEAD, SVG_OVERHEAD)

  expect(total).toBeLessThan(SVG_SOURCE_LIMIT)
})
