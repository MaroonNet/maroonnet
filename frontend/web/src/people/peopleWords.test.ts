import { expect, test } from 'vitest'
import type { Person, RosterPerson } from './people.ts'
import { checkedInRosterIds, historyLine, matches, personLine, personName, rosterName } from './peopleWords.ts'

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

test('a person\'s line in the list says what they carry', () => {
    expect(personLine(person(1, 'Ana', 'Ruiz', { team_id: 4, group_id: 2 }))).toBe('Radio 4 · Group 2')
    expect(personLine(person(1, 'Ana', 'Ruiz', { team_id: 4 }))).toBe('Radio 4 · No group')
    expect(personLine(person(1, 'Ana', 'Ruiz'))).toBe('No radio')
    expect(personLine(person(1, 'Searcher', '#1', { placeholder: true }))).toBe('Placeholder')
    expect(personLine(person(1, 'Searcher', '#1', { placeholder: true, team_id: 4 }))).toBe('Placeholder · Radio 4 · No group')
})

test('each history event has its words', () => {
    expect(historyLine({ time: '', what: 'checked_in', team_id: null })).toBe('Checked in')
    expect(historyLine({ time: '', what: 'checked_out', team_id: null })).toBe('Checked out')
    expect(historyLine({ time: '', what: 'took_radio', team_id: 4 })).toBe('Started carrying Radio 4')
    expect(historyLine({ time: '', what: 'left_radio', team_id: 4 })).toBe('Handed back Radio 4')
})
