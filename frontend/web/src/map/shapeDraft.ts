import { onOrInside, type Bounds, type Position } from './geo.ts'

// A shape drawn one corner at a time, and the rules it follows. These are plain functions:
// each takes a draft and answers with a new one, so the drawing on the map
// (drawCustomShape.ts) only has to keep the latest.

// A sector is sent to the phones in one radio packet, which holds at most 24 corners.
export const MOST_CORNERS = 24

export type ShapeDraft = {
    corners: Position[]   // in the order clicked
    undone: Position[]    // corners taken away by Undo, the last one undone at the end
}

export const EMPTY_DRAFT: ShapeDraft = { corners: [], undone: [] }

// Why a click was not taken: the shape already has the most corners, or the new side
// would cross or touch another.
export type Refusal = 'full' | 'crosses'

// Adds a corner where the user clicked. A click past the search area line puts the corner
// on the line. A refused click leaves the draft as it was.
export function addCorner(draft: ShapeDraft, place: Position, area: Bounds): { draft: ShapeDraft, refused: Refusal | null } {
    if (draft.corners.length >= MOST_CORNERS) return { draft, refused: 'full' }
    const corner = onOrInside(place, area)
    const corners = [...draft.corners, corner]
    const repeated = draft.corners.some((c) => c.lat === corner.lat && c.lon === corner.lon)
    if (repeated || sidesCross(corners, false)) return { draft, refused: 'crosses' }
    return { draft: { corners, undone: [] }, refused: null }
}

// Takes the last corner away. Redo can put it back.
export function undoCorner(draft: ShapeDraft): ShapeDraft {
    const last = draft.corners.at(-1)
    if (!last) return draft
    return { corners: draft.corners.slice(0, -1), undone: [...draft.undone, last] }
}

// Puts back the corner Undo last took away. It was allowed before, and the corners before
// it are the same, so it is allowed again.
export function redoCorner(draft: ShapeDraft): ShapeDraft {
    const next = draft.undone.at(-1)
    if (!next) return draft
    return { corners: [...draft.corners, next], undone: draft.undone.slice(0, -1) }
}

// Closes the shape: the last corner joins back to the first. It needs three corners, and
// the closing side may not cross another.
export function closeShape(draft: ShapeDraft): { corners: Position[] } | { refused: 'too-few' | 'crosses' } {
    if (draft.corners.length < 3) return { refused: 'too-few' }
    if (sidesCross(draft.corners, true)) return { refused: 'crosses' }
    return { corners: draft.corners }
}

// Whether any two sides cross or touch, with the same rule the backend uses
// (backend/sectors/shape.py). closed: the last corner joins back to the first. Degrees are
// treated as a flat grid, which is close enough at the size of a sector.
function sidesCross(corners: Position[], closed: boolean): boolean {
    const count = corners.length
    const sides = closed ? count : count - 1
    const corner = (i: number) => corners[i % count]
    for (let i = 0; i < sides; i++) {
        for (let j = i + 1; j < sides; j++) {
            if (j === i + 1) {
                // Neighbours: side i ends where side j starts.
                if (doublesBack(corner(i), corner(i + 1), corner(j + 1))) return true
            } else if (closed && i === 0 && j === sides - 1) {
                // The last side ends where the first starts.
                if (doublesBack(corner(j), corner(0), corner(1))) return true
            } else if (meet(corner(i), corner(i + 1), corner(j), corner(j + 1))) {
                return true
            }
        }
    }
    return false
}

// Whether two neighbouring sides lie on top of each other: the path goes out to the shared
// corner and comes straight back along the same line.
function doublesBack(before: Position, shared: Position, after: Position): boolean {
    const out = { lat: before.lat - shared.lat, lon: before.lon - shared.lon }
    const back = { lat: after.lat - shared.lat, lon: after.lon - shared.lon }
    const inLine = out.lat * back.lon - out.lon * back.lat === 0
    return inLine && out.lat * back.lat + out.lon * back.lon > 0
}

// Whether the side a-b and the side c-d cross or touch.
function meet(a: Position, b: Position, c: Position, d: Position): boolean {
    const abC = turn(a, b, c), abD = turn(a, b, d), cdA = turn(c, d, a), cdB = turn(c, d, b)
    if (abC * abD < 0 && cdA * cdB < 0) return true  // each side has the other's ends on opposite sides of it
    // A corner lying on the other side.
    return (abC === 0 && within(a, b, c)) || (abD === 0 && within(a, b, d))
        || (cdA === 0 && within(c, d, a)) || (cdB === 0 && within(c, d, b))
}

// Which way the path a to b to c turns: one sign for left, the other for right, zero in a line.
function turn(a: Position, b: Position, c: Position): number {
    return (b.lat - a.lat) * (c.lon - a.lon) - (b.lon - a.lon) * (c.lat - a.lat)
}

// Whether c, already known to be in line with a and b, lies between them.
function within(a: Position, b: Position, c: Position): boolean {
    return Math.min(a.lat, b.lat) <= c.lat && c.lat <= Math.max(a.lat, b.lat)
        && Math.min(a.lon, b.lon) <= c.lon && c.lon <= Math.max(a.lon, b.lon)
}
