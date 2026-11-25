import { createContext, useContext } from 'react'
import { ask } from '../mission/mission.ts'

// A roster person as the backend answers them (backend/people/roster.py). The roster is
// everyone the team knows, kept between missions.
export type RosterPerson = {
    id: number
    first_name: string
    middle_initial: string | null
    last_name: string
    phone: string | null
}

// What is typed in for a roster person.
export type PersonDetails = Omit<RosterPerson, 'id'>

// One line of a person's history.
export type PersonEvent = {
    time: string  // UTC
    what: 'checked_in' | 'checked_out' | 'took_radio' | 'left_radio'
    team_id: number | null  // the radio, for the two radio events
}

// A person of the open mission as the backend answers them (backend/people/mission_people.py).
export type Person = {
    id: number
    first_name: string
    last_name: string
    checked_in: boolean
    in_time: string | null      // their latest check-in this session; none: not yet checked in
    out_time: string | null     // when that check-in ended, if it has
    in_roster: boolean          // someone in the roster has this first and last name
    roster_id: number | null    // that roster person, when there is exactly one
    phone: string | null        // their phone number, from the roster
    team_id: number | null      // the radio they carry
    node_num: number | null     // that radio's node number
    group_id: number | null     // the group that radio is in
    shares: string[]            // the names of the others carrying the same radio
    last_on_radio: boolean      // nobody else carries their radio
    placeholder: boolean        // a stand-in such as "Searcher #1"
    can_remove: boolean         // a placeholder that has never carried a radio
    history: PersonEvent[]      // oldest first
}

// The backend's roster routes (backend/people/roster_routes.py).
export const loadRoster = () => ask<RosterPerson[]>('/api/roster')
export const addToRoster = (details: PersonDetails) => ask<RosterPerson>('/api/roster', 'POST', details)
export const changeRosterPerson = (id: number, details: PersonDetails) => ask<RosterPerson>(`/api/roster/${id}`, 'PUT', details)
export const deleteRosterPerson = (id: number) => ask<null>(`/api/roster/${id}`, 'DELETE')

// The backend's routes for the people in the open mission (backend/people/routes.py).
export const loadPeople = () => ask<Person[]>('/api/mission/people')
export const checkInFromRoster = (roster_id: number) => ask<Person>('/api/mission/people/check-in', 'POST', { roster_id })
export const checkIn = (id: number) => ask<Person>(`/api/mission/people/${id}/check-in`, 'POST')
export const checkOut = (id: number) => ask<Person>(`/api/mission/people/${id}/check-out`, 'POST')
export const addPlaceholder = () => ask<Person>('/api/mission/people/placeholders', 'POST')
export const replacePlaceholder = (id: number, roster_id: number) => ask<Person>(`/api/mission/people/${id}/replace`, 'POST', { roster_id })
export const removePlaceholder = (id: number) => ask<null>(`/api/mission/people/${id}`, 'DELETE')
export const saveToRoster = (id: number) => ask<Person>(`/api/mission/people/${id}/save-to-roster`, 'POST')

// The board: the roster and the open mission's people, kept in one place that any
// component can read.
export type PeopleBoard = {
    roster: RosterPerson[]  // by last name
    people: Person[]        // none while no mission is open
    // Waits for one of the requests above, then reads the roster and the people again, so
    // the screen always shows what is saved. One change can reach both lists: renaming a
    // roster person renames them in the mission. The answer is empty when it worked, and
    // the reason when it did not.
    run: (request: Promise<unknown>) => Promise<string>
}

// A component drawn with no PeopleProvider above it, as in a test of one component, reads
// this board: nobody, and nothing can be changed.
export const PeopleContext = createContext<PeopleBoard>({
    roster: [],
    people: [],
    run: async () => 'There is no people board.',
})

// What a component calls to read the board.
export function usePeople(): PeopleBoard {
    return useContext(PeopleContext)
}
