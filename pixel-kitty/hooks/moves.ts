/**
 * The pixel-kitty moves, as SVG frames and the order each move plays them.
 *
 * Special Notes:
 *
 * - Written by tools/build_frames.py. Rebuild rather than edit.
 */

import { FRAMES_0 } from './frames_0'

export const KITTY_WIDTH = 62
export const KITTY_HEIGHT = 42

// Distinct frames, drawn on rows offset by half a pixel, split across files the engine can read.
export const KITTY_FRAMES = [...FRAMES_0]

// Each move is the list of frames it shows, one per slot.
export const KITTY_MOVES: Record<string, number[]> = {"dance": [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38]}
