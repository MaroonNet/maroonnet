import type { MissionStatus, OpenMission } from '../mission/mission.ts'
import type { Person } from '../people/people.ts'
import type { Group, Radio } from './teams.ts'
import type { Track } from './tracks.ts'

// A made-up mission for the team tests, shaped like Arizona07: eight radios, three groups.
//
//   Group 1 (holds S4)   Radio 1: Marcus Ibarra, Tessa Lindqvist.  Radio 2: Priya Raman.
//   Group 2              Radio 7: Ana Morales.
//   Group 3              no teams
//   No group             Radio 4: Diego Alas.
//   Nobody on it         Radio 5 (searcher), Radio 6 (relay)
//   Command post         Radio 8: Ellen Brandt
//
// Naomi Feld and the placeholder Searcher #1 are checked in with no radio. Wes Hallam is
// not checked in.

// Arizona times: 4:19 am on April 14, 2025 is 11:19 UTC.
export function arizona(status: MissionStatus = 'active'): OpenMission {
    return {
        id: 'az07', name: 'Arizona07', time_zone: 'America/Phoenix', status, session: 1,
        start_time: '2025-04-14T03:30:00Z', end_time: null, sessions: [], asks_to_continue: false,
    }
}

function person(id: number, first_name: string, last_name: string, team_id: number | null, extra: Partial<Person> = {}): Person {
    return {
        id, first_name, last_name, checked_in: true, in_time: '2025-04-14T03:30:28Z', out_time: null,
        in_roster: true, roster_id: id, phone: null, team_id, node_num: null, group_id: null,
        shares: [], last_on_radio: false, placeholder: false, can_remove: false, history: [], ...extra,
    }
}

export const PEOPLE: Person[] = [
    person(1, 'Marcus', 'Ibarra', 1),
    person(2, 'Tessa', 'Lindqvist', 1),
    person(4, 'Priya', 'Raman', 2),
    person(9, 'Naomi', 'Feld', null),
    person(10, 'Diego', 'Alas', 4),
    person(16, 'Ellen', 'Brandt', 8),
    person(17, 'Wes', 'Hallam', null, { checked_in: false, out_time: '2025-04-14T08:10:00Z' }),
    person(18, 'Ana', 'Morales', 7),
    person(22, 'Searcher', '#1', null, { placeholder: true, in_roster: false, roster_id: null }),
]

const carrier = (id: number) => {
    const found = PEOPLE.find((p) => p.id === id)!
    return { id, name: `${found.first_name} ${found.last_name}`, placeholder: found.placeholder }
}
const at = (time: string) => ({ time, lat: 31.5063, lon: -110.6775, elevation: 1500 })

export const RADIOS: Radio[] = [
    { id: 1, node_num: 3663644600, kind: 'searcher', people: [carrier(1), carrier(2)], group_id: 1, last_position: at('2025-04-14T11:19:00Z') },
    { id: 2, node_num: 1128083228, kind: 'searcher', people: [carrier(4)], group_id: 1, last_position: at('2025-04-14T11:18:00Z') },
    { id: 4, node_num: 2134581666, kind: 'searcher', people: [carrier(10)], group_id: null, last_position: null },
    { id: 5, node_num: 3876229574, kind: 'searcher', people: [], group_id: null, last_position: null },
    { id: 6, node_num: 1016025774, kind: 'relay', people: [], group_id: null, last_position: null },
    { id: 7, node_num: 2603508945, kind: 'searcher', people: [carrier(18)], group_id: 2, last_position: at('2025-04-14T11:17:00Z') },
    { id: 8, node_num: 1564517367, kind: 'command_post', people: [carrier(16)], group_id: null, last_position: at('2025-04-14T11:20:00Z') },
]

// Two tracks: Radio 1 walked in Group 1, then in Group 3; Radio 4 in Group 2, then in none.
// A piece after the first starts on the last point of the piece before it.
export const TRACKS: Track[] = [
    { radio_id: 1, pieces: [
        { group_id: 1, points: [[-110.677, 31.506], [-110.675, 31.508], [-110.673, 31.509]] },
        { group_id: 3, points: [[-110.673, 31.509], [-110.677, 31.506]] },
    ] },
    { radio_id: 4, pieces: [
        { group_id: 2, points: [[-110.677, 31.506], [-110.68, 31.504]] },
        { group_id: null, points: [[-110.68, 31.504], [-110.677, 31.506]] },
    ] },
]

export const GROUPS: Group[] = [
    { id: 1, radio_ids: [1, 2], sector: { id: 4, name: 'S4' } },
    { id: 2, radio_ids: [7], sector: null },
    { id: 3, radio_ids: [], sector: null },
]
