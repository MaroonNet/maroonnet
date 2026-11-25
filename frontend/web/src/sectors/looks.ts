import { groupColor } from '../teams/teamWords.ts'
import type { Sector } from './sectors.ts'

// How a sector looks on the map.
//   drawn      a red outline
//   assigned   a red outline, labeled with its group: "S4 → G3"
//   searching  its group's color, outline and a light fill
//   partial    an orange outline with stripes
//   completed  green, outline and a light fill
// A partial sector given to a group again keeps its stripes, with the group in its label,
// until a team of that group enters it.
export type Look = 'drawn' | 'assigned' | 'searching' | 'partial' | 'completed'

export function lookOf(sector: Sector): Look {
    if (sector.status !== 'drawn') return sector.status
    return sector.group_id !== null ? 'assigned' : 'drawn'
}

// The map library takes colors as text: --color-red and --color-green in index.css, and
// an orange for partial sectors. A searching sector takes its group's color instead.
export const SECTOR_COLORS: Record<Exclude<Look, 'searching'>, string> = {
    drawn: '#c9302d', assigned: '#c9302d', partial: '#e57600', completed: '#218a45',
}

// The color of a sector's outline and name.
export function sectorColor(sector: Sector): string {
    const look = lookOf(sector)
    if (look !== 'searching') return SECTOR_COLORS[look]
    return sector.group_id !== null ? groupColor(sector.group_id) : SECTOR_COLORS.drawn
}

// A sector's name on the map. One a group holds names the group, in the map's short form.
export const mapLabel = (sector: Sector) => sector.group_id !== null ? `${sector.name} → G${sector.group_id}` : sector.name

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
