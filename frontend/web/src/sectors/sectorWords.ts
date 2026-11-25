import { formatTime } from '../mission/missionTime.ts'
import type { Sector } from './sectors.ts'

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

// What can be done with the sector, as its card says it.
export function sectorNote(sector: Sector): string {
    if (sector.status === 'completed') return 'History. Kept for the after-action review.'
    if (sector.status === 'partial') return 'Searched in part. It can be assigned again.'
    if (sector.status === 'searching') return 'Shape is locked. It can be completed and replaced, not edited.'
    return sector.can_edit ? 'Not sent yet. Shape can still be edited.' : 'Sent before. Shape is locked.'
}
