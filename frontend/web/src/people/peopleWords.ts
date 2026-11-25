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

// The line beside a person's name in the list: what they carry.
export function personLine(person: Person): string {
    const carrying = person.team_id === null ? null : `${radioLabel(person.team_id)} · ${groupLabel(person.group_id)}`
    if (person.placeholder) return carrying ? `Placeholder · ${carrying}` : 'Placeholder'
    return carrying ?? 'No radio'
}

// One line of a person's history.
export function historyLine(event: PersonEvent): string {
    switch (event.what) {
        case 'checked_in': return 'Checked in'
        case 'checked_out': return 'Checked out'
        case 'took_radio': return `Started carrying ${radioLabel(event.team_id!)}`
        case 'left_radio': return `Handed back ${radioLabel(event.team_id!)}`
    }
}
