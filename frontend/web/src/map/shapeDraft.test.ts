import { expect, test } from 'vitest'
import type { Bounds, Position } from './geo.ts'
import { addCorner, closeShape, EMPTY_DRAFT, redoCorner, undoCorner, type ShapeDraft } from './shapeDraft.ts'

const AREA: Bounds = { min_lat: 31.3926, min_lon: -110.8083, max_lat: 31.619, max_lon: -110.544 }

// Adds each place in turn, as clicks would, and answers with the draft.
function clicks(...places: [number, number][]): ShapeDraft {
    return places.reduce((draft, [lat, lon]) => addCorner(draft, { lat, lon }, AREA).draft, EMPTY_DRAFT)
}
const at = (lat: number, lon: number): Position => ({ lat, lon })

// A five-corner shape: a square with a point pulled out of its right side.
const FIVE: [number, number][] = [[31.50, -110.70], [31.52, -110.70], [31.52, -110.68], [31.51, -110.67], [31.50, -110.68]]

test('a click adds a corner', () => {
    const { draft, refused } = addCorner(EMPTY_DRAFT, at(31.5, -110.7), AREA)
    expect(draft.corners).toEqual([at(31.5, -110.7)])
    expect(refused).toBeNull()
})

test('a click past the search area line puts the corner on the line, at the nearest spot', () => {
    const { draft } = addCorner(clicks([31.5, -110.6]), at(31.5, -110.5), AREA)
    expect(draft.corners[1]).toEqual(at(31.5, -110.544))
})

test('a 25th corner is refused, and the shape so far is kept', () => {
    // A zigzag of 24 corners, which no side crosses.
    const zigzag = clicks(...Array.from({ length: 24 }, (_, i): [number, number] => [31.5 + 0.001 * (i % 2), -110.7 + 0.001 * i]))
    expect(zigzag.corners).toHaveLength(24)

    const { draft, refused } = addCorner(zigzag, at(31.52, -110.7), AREA)

    expect(refused).toBe('full')
    expect(draft).toBe(zigzag)
})

test('a click that would make the new side cross an earlier one is refused', () => {
    const square = clicks([31.50, -110.70], [31.52, -110.70], [31.52, -110.68], [31.50, -110.68])
    const { draft, refused } = addCorner(square, at(31.53, -110.69), AREA)  // back across the top side
    expect(refused).toBe('crosses')
    expect(draft).toBe(square)
})

test('a click straight back along the last side, or on a corner already placed, is refused', () => {
    const line = clicks([31.50, -110.70], [31.52, -110.70])
    expect(addCorner(line, at(31.51, -110.70), AREA).refused).toBe('crosses')   // folds back on the last side
    expect(addCorner(clicks([31.50, -110.70], [31.52, -110.70], [31.52, -110.68]), at(31.50, -110.70), AREA).refused)
        .toBe('crosses')                                                          // on the first corner
})

test('Undo takes the last corner away, and Redo puts it back', () => {
    const five = clicks(...FIVE)
    const undone = undoCorner(five)
    expect(undone.corners).toEqual(five.corners.slice(0, 4))
    expect(redoCorner(undone).corners).toEqual(five.corners)
})

test('Undo and Redo do nothing when there is nothing to undo or redo', () => {
    expect(undoCorner(EMPTY_DRAFT)).toBe(EMPTY_DRAFT)
    const five = clicks(...FIVE)
    expect(redoCorner(five)).toBe(five)
})

test('a new corner after Undo means the undone corner can no longer be redone', () => {
    const changed = addCorner(undoCorner(clicks(...FIVE)), at(31.505, -110.665), AREA).draft
    expect(changed.undone).toEqual([])
    expect(redoCorner(changed)).toBe(changed)
})

test('a shape closes with three corners or more', () => {
    expect(closeShape(clicks(FIVE[0], FIVE[1]))).toEqual({ refused: 'too-few' })
    expect(closeShape(clicks(FIVE[0], FIVE[1], FIVE[2]))).toEqual({ corners: clicks(FIVE[0], FIVE[1], FIVE[2]).corners })
})

test('a shape whose closing side would cross another side is refused', () => {
    // A Z: closing it runs back across its middle side.
    const z = clicks([31.52, -110.70], [31.52, -110.68], [31.50, -110.70], [31.50, -110.68])
    expect(closeShape(z)).toEqual({ refused: 'crosses' })
})

test('five corners drawn, one undone and redone, then closed', () => {
    const draft = redoCorner(undoCorner(clicks(...FIVE)))
    expect(closeShape(draft)).toEqual({ corners: FIVE.map(([lat, lon]) => at(lat, lon)) })
})
