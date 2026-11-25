import { ask } from '../mission/mission.ts'

// The radios and groups of the open mission, as the backend answers them
// (backend/teams/teams.py). A radio is a team while someone carries it. They are kept on
// the people board (people/people.ts), since a change to a team changes its people too.

export type RadioKind = 'searcher' | 'command_post' | 'relay' | 'aerial'

// A person carrying a radio.
export type Carrier = {
    id: number
    name: string
    placeholder: boolean  // a stand-in such as "Searcher #1"
}

export type RadioPosition = {
    time: string  // UTC
    lat: number
    lon: number
    elevation: number | null  // meters
}

// A radio. Its id is the number in its label: radio 4 is "Radio 4".
export type Radio = {
    id: number
    node_num: number
    kind: RadioKind
    people: Carrier[]                       // who carries it; with nobody, it is not a team
    group_id: number | null
    last_position: RadioPosition | null     // its newest position report
}

export type Group = {
    id: number
    radio_ids: number[]                             // its teams; a group with none stays listed
    sector: { id: number, name: string } | null     // the sector it holds
}

// The backend's routes (backend/teams/routes.py). A team's id is its radio's id.
export const loadRadios = () => ask<Radio[]>('/api/mission/radios')
export const loadGroups = () => ask<Group[]>('/api/mission/groups')
export const makeTeam = (radio_id: number, searcher_ids: number[], group_id: number | null) =>
    ask<Radio>('/api/mission/teams', 'POST', { radio_id, searcher_ids, group_id })
export const changeTeam = (radio_id: number, searcher_ids: number[], group_id: number | null) =>
    ask<Radio>(`/api/mission/teams/${radio_id}`, 'PUT', { searcher_ids, group_id })
export const makeGroup = (radio_ids: number[]) => ask<Group>('/api/mission/groups', 'POST', { radio_ids })
export const changeGroup = (group_id: number, radio_ids: number[]) => ask<Group>(`/api/mission/groups/${group_id}`, 'PUT', { radio_ids })
