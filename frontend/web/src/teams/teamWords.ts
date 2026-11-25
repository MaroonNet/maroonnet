import { formatTime } from '../mission/missionTime.ts'
import type { Person } from '../people/people.ts'
import { groupLabel } from '../people/peopleWords.ts'
import type { Group, Radio, RadioKind } from './teams.ts'

// The words and colors the Groups & Teams panel, the team card and the Mesh panel use, and
// the readings of which radios are teams.

// A group's color, by its number: eight, used in order and again after the eighth. The
// first four are the mockup's; none is the red of an alert or the green of a completed sector.
export const GROUP_COLORS = [
    'oklch(0.52 0.15 255)',  // blue
    'oklch(0.52 0.15 315)',  // purple
    'oklch(0.64 0.15 55)',   // orange
    'oklch(0.56 0.1 200)',   // teal
    'oklch(0.58 0.17 350)',  // pink
    'oklch(0.55 0.11 110)',  // olive
    'oklch(0.42 0.13 285)',  // indigo
    'oklch(0.47 0.07 60)',   // brown
]
export const groupColor = (groupId: number) => GROUP_COLORS[(groupId - 1) % GROUP_COLORS.length]

export const KIND_LABELS: Record<RadioKind, string> = {
    searcher: 'Searcher', command_post: 'Command post', relay: 'Relay', aerial: 'Aerial',
}

// The teams: searcher radios with someone on them. The command post radio and a relay are
// never teams, whoever carries them.
export const teamsOf = (radios: Radio[]) => radios.filter((radio) => radio.kind === 'searcher' && radio.people.length > 0)

// The radios that can be made a team: searcher radios with nobody on them.
export const freeRadios = (radios: Radio[]) => radios.filter((radio) => radio.kind === 'searcher' && radio.people.length === 0)

// The people who can be put on a team: checked in, and carrying no radio.
export const freePeople = (people: Person[]) => people.filter((person) => person.checked_in && person.team_id === null)

// Who carries a radio: "Diego Alas, Corey Greene". With a most, the rest are counted: "+2".
export function carriedBy(radio: Radio, most = Infinity): string {
    if (radio.people.length === 0) return 'Nobody'
    const names = radio.people.slice(0, most).map((person) => person.name).join(', ')
    const more = radio.people.length - most
    return more > 0 ? `${names} +${more}` : names
}

// The time of a radio's newest position, in the mission's time zone.
export function lastPosition(radio: Radio, zone: string): string {
    return radio.last_position ? `Last position ${formatTime(radio.last_position.time, zone)}` : 'No position yet'
}

// A group's line in the list: "Group 1 · S4", or "Group 3 · no teams".
export function groupLine(group: Group): string {
    const about = group.radio_ids.length === 0 ? 'no teams' : group.sector?.name
    return about ? `${groupLabel(group.id)} · ${about}` : groupLabel(group.id)
}
