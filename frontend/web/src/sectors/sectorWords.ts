import { MOST_CORNERS } from '../map/shapeDraft.ts'
import { formatTime } from '../mission/missionTime.ts'
import { groupLabel, radioLabel } from '../people/peopleWords.ts'
import type { Sector, Send } from './sectors.ts'

// The hint line when a corner added at a side's middle is refused.
export const FULL = `A sector has at most ${MOST_CORNERS} corners.`

// The words the Sectors panel, a sector's card, the legend and the Mission panel use for a
// sector.

// Where a sector stands, as the screen says it. "Assigned" is not a saved status: it is a
// drawn or partial sector that a group holds and no team of that group has entered yet.
export type Standing = 'drawn' | 'assigned' | 'searching' | 'partial' | 'completed'

// In the order of a sector's life.
export const STANDINGS: Standing[] = ['drawn', 'assigned', 'searching', 'partial', 'completed']

export const STATUS_LABELS: Record<Standing, string> = {
    drawn: 'Drawn', assigned: 'Assigned', searching: 'Searching', partial: 'Partial', completed: 'Completed',
}

export function standingOf(sector: Sector): Standing {
    if (sector.status === 'completed' || sector.status === 'searching') return sector.status
    return sector.group_id !== null ? 'assigned' : sector.status
}

export const statusLabel = (sector: Sector) => STATUS_LABELS[standingOf(sector)]

// The line under a sector's name in the Sectors panel. zone: the mission's time zone.
export function sectorLine(sector: Sector, zone: string): string {
    const standing = standingOf(sector)
    if (standing === 'completed' && sector.completed_time) return `Completed ${formatTime(sector.completed_time, zone)}`
    if (standing === 'partial') return 'Searched in part'
    if (standing === 'searching') return sector.group_id === null ? 'Being searched' : `Being searched by ${groupLabel(sector.group_id)}`
    if (standing === 'assigned') return `Assigned to ${groupLabel(sector.group_id)}`
    return 'Unassigned'
}

// Names as a sentence writes them: "S1", "S1 and S2", "S1, S2 and S3".
export function nameList(names: string[]): string {
    return names.length === 1 ? names[0] : `${names.slice(0, -1).join(', ')} and ${names.at(-1)}`
}

// What can be done with the sector, as its card says it.
export function sectorNote(sector: Sector): string {
    const standing = standingOf(sector)
    if (standing === 'completed') return 'History. Kept for the after-action review.'
    if (standing === 'partial') return 'Searched in part. It can be assigned again.'
    if (standing === 'searching' || standing === 'assigned') return 'Shape is locked. It can be completed and replaced, not edited.'
    return sector.can_edit ? 'Not sent yet. Shape can still be edited.' : 'Sent before. Shape is locked.'
}

// A sector's saved sends as one line: "Sent to Radios 1, 2, 3 · all acknowledged". A radio
// sent to more than once counts by its newest send. None for a sector never sent.
export function sendsLine(sends: Send[]): string | null {
    if (sends.length === 0) return null
    const newest = new Map<number, Send>()  // each radio's newest send; the sends come oldest first
    for (const send of sends) newest.set(send.radio_id, send)
    const radios = [...newest.keys()].sort((a, b) => a - b)
    const acknowledged = radios.filter((radio) => newest.get(radio)!.ack_time !== null).length
    const to = radios.length === 1 ? radioLabel(radios[0]) : `Radios ${radios.join(', ')}`
    return `Sent to ${to} · ${acknowledgedWords(acknowledged, radios.length)}`
}

function acknowledgedWords(acknowledged: number, of: number): string {
    if (of === 1) return acknowledged ? 'acknowledged' : 'not acknowledged'
    if (acknowledged === of) return 'all acknowledged'
    return acknowledged === 0 ? 'none acknowledged' : `${acknowledged} of ${of} acknowledged`
}
