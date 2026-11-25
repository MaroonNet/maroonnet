import { formatTime } from '../mission/missionTime.ts'
import { groupLabel, radioLabel } from '../people/peopleWords.ts'
import type { LogLine } from './log.ts'

// The words the Communication Log uses for a line, and its type filters.

// The types a line can be filtered by, in the order of the filter chips.
const TYPES = [
    { code: 'evidence', label: 'Evidence' },
    { code: 'found', label: 'Found' },
    { code: 'instruction', label: 'Instruction' },
    { code: 'out_of_sector', label: 'Out of sector' },
    { code: 'assignment', label: 'Assignment' },
]
export const FILTERS = [{ code: 'all', label: 'All' }, ...TYPES]

// A type's name. The mission file can list a type the app has no name for; it is shown by
// its code.
export const typeLabel = (code: string) => TYPES.find((type) => type.code === code)?.label ?? code

// A line's type. A sector line is an assignment.
export const typeOf = (line: LogLine) => line.kind === 'sector' ? 'assignment' : line.type

// The lines a filter shows: all of them, or those of one type.
export const shownBy = (lines: LogLine[], filter: string) =>
    filter === 'all' ? lines : lines.filter((line) => typeOf(line) === filter)

// Who a message went to or came from: "To Radio 4", "From Radio 1", "To Radios 1, 2",
// "Broadcast · 6 radios". A broadcast counts the radios it was saved for, which need not be
// every radio of the mission. A sector line names nobody.
export function who(line: LogLine): string {
    if (line.kind === 'sector') return ''
    const ids = line.radios.map((radio) => radio.radio_id)
    if (line.direction === 'in') return `From ${radioLabel(ids[0])}`
    if (line.addressing === 'broadcast') return `Broadcast · ${ids.length} ${ids.length === 1 ? 'radio' : 'radios'}`
    if (line.addressing === 'multicast') return `To Radios ${ids.join(', ')}`
    return `To ${radioLabel(ids[0])}`
}

// What a line says: a message's text, or what happened to a sector: "S1 assigned to
// Group 1", "S3 completed by Group 2", "S4 released by Group 3 (partial)".
export function words(line: LogLine): string {
    if (line.kind === 'message') return line.text
    const group = groupLabel(line.group_id)
    if (line.event === 'assigned') return `${line.sector_name} assigned to ${group}`
    return `${line.sector_name} ${line.event} by ${group}${line.partial ? ' (partial)' : ''}`
}

// When one radio acknowledged, in the mission's time zone.
export const receipt = (ackTime: string | null, zone: string) =>
    ackTime ? `acknowledged ${formatTime(ackTime, zone)}` : 'not acknowledged'

// A line that opens to list its radios: a send to several.
export const opens = (line: LogLine) => line.kind === 'message' && line.addressing !== 'direct'

// Whether a sent message was acknowledged: when, for a message to one radio; how many
// radios have, for a send to several. Only a message the command post sent has this.
export function acknowledged(line: LogLine, zone: string): string {
    if (line.kind === 'sector' || line.direction === 'in') return ''
    if (!opens(line)) return receipt(line.radios[0].ack_time, zone)
    return `${line.radios.filter((radio) => radio.ack_time).length} acknowledged`
}

// A whole line as one sentence, its parts in the order they are drawn:
// "11:24 pm · To Radio 4 · Instruction · Hold at the creek. · acknowledged 11:24 pm".
export function lineWords(line: LogLine, zone: string): string {
    const parts = [formatTime(line.time, zone), who(line), typeLabel(typeOf(line)), words(line), acknowledged(line, zone)]
    return parts.filter((part) => part !== '').join(' · ')
}
