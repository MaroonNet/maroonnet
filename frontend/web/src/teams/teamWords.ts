import { formatTime } from '../mission/missionTime.ts'
import type { Person } from '../people/people.ts'
import { groupLabel } from '../people/peopleWords.ts'
import type { Group, Radio, RadioKind } from './teams.ts'

// The words and colors the Groups & Teams panel, the team card and the Mesh panel use, and
// the readings of which radios are teams.

// A group's color, by its number: seven, used in order and again after the seventh. None
// is the red of an alert, the green of a completed sector or the orange of a partial one,
// since a sector being searched is drawn in its group's color. They are written as the map
// library reads a color.
export const GROUP_COLORS = [
    '#1f68bc',  // blue
    '#8949a3',  // purple
    '#c04688',  // pink
    '#00868c',  // teal
    '#76771a',  // olive
    '#483e90',  // indigo
    '#785130',  // brown
]
export const groupColor = (groupId: number) => GROUP_COLORS[(groupId - 1) % GROUP_COLORS.length]

// The color of a team on the map, and of the track it walked: its group's, or grey for a
// team in no group.
export const NO_GROUP_COLOR = '#6b6b6b'
export const teamColor = (groupId: number | null) => groupId === null ? NO_GROUP_COLOR : groupColor(groupId)

// A team's short name, and its group's, as the team's pill on the map has them: "R4", "G2".
export const mapName = (radioId: number) => `R${radioId}`
export const groupMapName = (groupId: number) => `G${groupId}`

// The teams that have a marker on the map: those whose radio has reported a position.
export const teamsOnMap = (radios: Radio[]) => teamsOf(radios).filter((radio) => radio.last_position !== null)

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
