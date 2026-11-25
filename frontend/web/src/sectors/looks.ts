import type { Sector } from './sectors.ts'

// How a sector looks on the map. Assigned (with its "S4 → G3" label) and Searching (in the
// group's color) are added with assigning, in D7; until then both look drawn.
export type Look = 'drawn' | 'partial' | 'completed'

export function lookOf(sector: Sector): Look {
    if (sector.status === 'completed') return 'completed'
    if (sector.status === 'partial') return 'partial'
    return 'drawn'
}

// The map library takes colors as text: --color-red and --color-green in index.css, and
// an orange for partial sectors.
export const SECTOR_COLORS: Record<Look, string> = { drawn: '#c9302d', partial: '#e57600', completed: '#218a45' }

// The name the stripe picture goes by on the map.
export const STRIPES = 'sector-stripes'

// The picture the map repeats over a partial sector: thin orange stripes rising to the
// right, on clear. It is 16 pixels square and shown at half size, so it stays sharp on a
// fine screen; 16 is a whole number of stripes, so the tiles meet with no seam.
export function stripesImage(): { width: number, height: number, data: Uint8Array } {
    const size = 16, every = 8, wide = 3  // a stripe every 8 pixels, 3 pixels wide
    const [red, green, blue] = [0xe5, 0x76, 0x00]  // SECTOR_COLORS.partial
    const data = new Uint8Array(size * size * 4)  // red, green, blue and opacity for each pixel
    for (let y = 0; y < size; y++) {
        for (let x = 0; x < size; x++) {
            if ((x + y) % every >= wide) continue  // clear between the stripes
            data.set([red, green, blue, 150], (y * size + x) * 4)
        }
    }
    return { width: size, height: size, data }
}
