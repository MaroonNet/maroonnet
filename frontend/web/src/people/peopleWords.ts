import type { Person, PersonEvent, RosterPerson } from './people.ts'

// The words the People panel and the Manage Roster dialog use, and the reading of which
// roster people are checked in.

// "Corey B. Greene", or "Corey Greene" with no initial.
export function rosterName(person: RosterPerson): string {
    const initial = person.middle_initial ? ` ${person.middle_initial}.` : ''
    return `${person.first_name}${initial} ${person.last_name}`
}

// A mission person's name. The mission file has no initial. A placeholder reads "Searcher #1".
export function personName(person: Person): string {
    return `${person.first_name} ${person.last_name}`
}

// By last name, with the placeholders after the real people.
export function inOrder(people: Person[]): Person[] {
    return [...people].sort((a, b) =>
        Number(a.placeholder) - Number(b.placeholder)
        || a.last_name.localeCompare(b.last_name, undefined, { numeric: true })
        || a.first_name.localeCompare(b.first_name))
}

// How the People panel's table is sorted: by which column, and whether the order is turned
// around. It starts by last name, A to Z.
export type PeopleSort = { by: 'first' | 'last' | 'radio' | 'group', reversed: boolean }
export const BY_LAST_NAME: PeopleSort = { by: 'last', reversed: false }

const text = (a: string, b: string) => a.localeCompare(b, undefined, { numeric: true })
// A missing number (no radio, no group) comes after every number.
const number = (a: number | null, b: number | null) => (a ?? Infinity) - (b ?? Infinity) || 0
const byLastName = (a: Person, b: Person) => text(a.last_name, b.last_name) || text(a.first_name, b.first_name)
const placeholdersAfter = (a: Person, b: Person) => Number(a.placeholder) - Number(b.placeholder)
const COMPARE: Record<PeopleSort['by'], (a: Person, b: Person) => number> = {
    last: byLastName,
    first: (a, b) => text(a.first_name, b.first_name) || text(a.last_name, b.last_name),
    radio: (a, b) => number(a.team_id, b.team_id) || placeholdersAfter(a, b) || byLastName(a, b),
    group: (a, b) => number(a.group_id, b.group_id) || number(a.team_id, b.team_id) || placeholdersAfter(a, b) || byLastName(a, b),
}
// Who stays at the end whichever way the table is turned: the placeholders when sorting by
// name, and the people with no radio, or in no group, when sorting by those.
const AT_END: Record<PeopleSort['by'], (person: Person) => boolean> = {
    last: (person) => person.placeholder,
    first: (person) => person.placeholder,
    radio: (person) => person.team_id === null,
    group: (person) => person.group_id === null,
}

// The people in the table's order. Those at the end are in A to Z order among themselves.
export function sortPeople(people: Person[], { by, reversed }: PeopleSort): Person[] {
    const atEnd = AT_END[by]
    const rest = people.filter((person) => !atEnd(person)).sort(COMPARE[by])
    return [...(reversed ? rest.reverse() : rest), ...people.filter(atEnd).sort(COMPARE[by])]
}

// Whether a name holds what was typed in the search box. Capitals do not matter.
export function matches(name: string, search: string): boolean {
    return name.toLowerCase().includes(search.trim().toLowerCase())
}

const nameKey = (first: string, last: string) => `${first.toLowerCase()} ${last.toLowerCase()}`

// The ids of the roster people who are checked in to the open mission. A mission person is
// tied to the roster by first and last name only, so of two roster people with one name,
// as many count as checked in as the mission has checked in under that name, lowest id first.
export function checkedInRosterIds(roster: RosterPerson[], people: Person[]): Set<number> {
    const present = new Map<string, number>()  // how many are checked in under each name
    for (const person of people) {
        if (!person.checked_in) continue
        const key = nameKey(person.first_name, person.last_name)
        present.set(key, (present.get(key) ?? 0) + 1)
    }
    const ids = new Set<number>()
    for (const person of [...roster].sort((a, b) => a.id - b.id)) {
        const key = nameKey(person.first_name, person.last_name)
        const left = present.get(key) ?? 0
        if (left > 0) {
            ids.add(person.id)
            present.set(key, left - 1)
        }
    }
    return ids
}

// The labels the demo uses in lists: "Radio 4", "Group 2".
export const radioLabel = (teamId: number) => `Radio ${teamId}`
export const groupLabel = (groupId: number | null) => groupId === null ? 'No group' : `Group ${groupId}`

// One line of a person's history.
export function historyLine(event: PersonEvent): string {
    switch (event.what) {
        case 'checked_in': return 'Checked in'
        case 'checked_out': return 'Checked out'
        case 'took_radio': return `Started carrying ${radioLabel(event.team_id!)}`
        case 'left_radio': return `Handed back ${radioLabel(event.team_id!)}`
    }
}
