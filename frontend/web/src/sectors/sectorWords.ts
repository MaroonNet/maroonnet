import { MOST_CORNERS } from '../map/shapeDraft.ts'
import { formatTime } from '../mission/missionTime.ts'
import type { Sector } from './sectors.ts'

// The hint line when a corner added at a side's middle is refused.
export const FULL = `A sector has at most ${MOST_CORNERS} corners.`

// The words the Sectors panel and a sector's card use for a sector. Assigned, with its
// group, is added with assigning in D7; until then a sector a group holds reads by its
// saved status.

export const STATUS_LABELS: Record<Sector['status'], string> = {
    drawn: 'Drawn', searching: 'Searching', partial: 'Partial', completed: 'Completed',
}

// The line under a sector's name in the Sectors panel. zone: the mission's time zone.
export function sectorLine(sector: Sector, zone: string): string {
    if (sector.status === 'completed' && sector.completed_time) return `Completed ${formatTime(sector.completed_time, zone)}`
    if (sector.status === 'partial') return 'Searched in part'
    if (sector.status === 'searching') return 'Being searched'
    return 'Unassigned'
}

// Names as a sentence writes them: "S1", "S1 and S2", "S1, S2 and S3".
export function nameList(names: string[]): string {
    return names.length === 1 ? names[0] : `${names.slice(0, -1).join(', ')} and ${names.at(-1)}`
}

// What can be done with the sector, as its card says it.
export function sectorNote(sector: Sector): string {
    if (sector.status === 'completed') return 'History. Kept for the after-action review.'
    if (sector.status === 'partial') return 'Searched in part. It can be assigned again.'
    if (sector.status === 'searching') return 'Shape is locked. It can be completed and replaced, not edited.'
    return sector.can_edit ? 'Not sent yet. Shape can still be edited.' : 'Sent before. Shape is locked.'
}
