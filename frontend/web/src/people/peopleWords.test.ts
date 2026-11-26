import { expect, test } from 'vitest'
import type { Person, RosterPerson } from './people.ts'
import { BY_LAST_NAME, checkedInRosterIds, historyLine, matches, personName, rosterName, sortPeople } from './peopleWords.ts'

function rosterPerson(id: number, first_name: string, last_name: string, middle_initial: string | null = null): RosterPerson {
    return { id, first_name, middle_initial, last_name, phone: null }
}

function person(id: number, first_name: string, last_name: string, extra: Partial<Person> = {}): Person {
    return {
        id, first_name, last_name, checked_in: true, in_time: '2025-04-14T03:30:28Z', out_time: null,
        in_roster: false, roster_id: null, phone: null, team_id: null, node_num: null, group_id: null,
        shares: [], last_on_radio: false, placeholder: false, can_remove: false, history: [], ...extra,
    }
}

test('a roster name has the middle initial when there is one', () => {
    expect(rosterName(rosterPerson(1, 'Corey', 'Greene', 'B'))).toBe('Corey B. Greene')
    expect(rosterName(rosterPerson(2, 'Corey', 'Greene'))).toBe('Corey Greene')
    expect(personName(person(1, 'Searcher', '#2'))).toBe('Searcher #2')
})

test('a search matches any part of a name, whatever the capitals', () => {
    expect(matches('Corey B. Greene', 'gree')).toBe(true)
    expect(matches('Corey B. Greene', ' COREY ')).toBe(true)
    expect(matches('Corey B. Greene', 'ana')).toBe(false)
    expect(matches('Corey B. Greene', '')).toBe(true)
})

test('a roster person counts as checked in when a checked-in mission person has their name', () => {
    const roster = [rosterPerson(1, 'Ana', 'Ruiz'), rosterPerson(2, 'Ben', 'Cho'), rosterPerson(3, 'Cy', 'Dunn')]
    const people = [person(1, 'ana', 'RUIZ'), person(2, 'Ben', 'Cho', { checked_in: false })]
    expect([...checkedInRosterIds(roster, people)]).toEqual([1])
})

test('of two roster people with one name, as many count as checked in as the mission has', () => {
    const roster = [rosterPerson(1, 'Corey', 'Greene'), rosterPerson(2, 'Corey', 'Greene', 'B')]
    expect([...checkedInRosterIds(roster, [person(1, 'Corey', 'Greene')])]).toEqual([1])
    expect([...checkedInRosterIds(roster, [person(1, 'Corey', 'Greene'), person(2, 'Corey', 'Greene')])]).toEqual([1, 2])
})

test('each history event has its words', () => {
    expect(historyLine({ time: '', what: 'checked_in', team_id: null })).toBe('Checked in')
    expect(historyLine({ time: '', what: 'checked_out', team_id: null })).toBe('Checked out')
    expect(historyLine({ time: '', what: 'took_radio', team_id: 4 })).toBe('Started carrying Radio 4')
    expect(historyLine({ time: '', what: 'left_radio', team_id: 4 })).toBe('Handed back Radio 4')
})

// Sorting the People panel's table.

const CREW = [
    person(1, 'Marcus', 'Ibarra', { team_id: 1, group_id: 1 }),
    person(2, 'Diego', 'Alas', { team_id: 4 }),
    person(3, 'Ana', 'Morales', { team_id: 7, group_id: 2 }),
    person(4, 'Naomi', 'Feld'),
    person(5, 'Searcher', '#1', { placeholder: true, team_id: 2, group_id: 1 }),
    person(6, 'Tessa', 'Lindqvist', { team_id: 1, group_id: 1 }),
]
const names = (people: Person[]) => people.map(personName)

test('the table sorts by last name or first name, with placeholders after everyone whichever way it is turned', () => {
    expect(names(sortPeople(CREW, BY_LAST_NAME))).toEqual(['Diego Alas', 'Naomi Feld', 'Marcus Ibarra', 'Tessa Lindqvist', 'Ana Morales', 'Searcher #1'])
    expect(names(sortPeople(CREW, { by: 'last', reversed: true }))).toEqual(['Ana Morales', 'Tessa Lindqvist', 'Marcus Ibarra', 'Naomi Feld', 'Diego Alas', 'Searcher #1'])
    expect(names(sortPeople(CREW, { by: 'first', reversed: false }))).toEqual(['Ana Morales', 'Diego Alas', 'Marcus Ibarra', 'Naomi Feld', 'Tessa Lindqvist', 'Searcher #1'])
})

test('by radio, people come in radio order and by last name on one radio, with those carrying none at the end', () => {
    expect(names(sortPeople(CREW, { by: 'radio', reversed: false }))).toEqual(['Marcus Ibarra', 'Tessa Lindqvist', 'Searcher #1', 'Diego Alas', 'Ana Morales', 'Naomi Feld'])
    expect(names(sortPeople(CREW, { by: 'radio', reversed: true }))).toEqual(['Ana Morales', 'Diego Alas', 'Searcher #1', 'Tessa Lindqvist', 'Marcus Ibarra', 'Naomi Feld'])
})

test('by group, people come in group order, then radio order, with those in no group at the end', () => {
    expect(names(sortPeople(CREW, { by: 'group', reversed: false }))).toEqual(['Marcus Ibarra', 'Tessa Lindqvist', 'Searcher #1', 'Ana Morales', 'Diego Alas', 'Naomi Feld'])
    expect(names(sortPeople(CREW, { by: 'group', reversed: true }))).toEqual(['Ana Morales', 'Searcher #1', 'Tessa Lindqvist', 'Marcus Ibarra', 'Diego Alas', 'Naomi Feld'])
})
