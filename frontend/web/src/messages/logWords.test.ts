import { expect, test } from 'vitest'
import { acknowledged, FILTERS, opens, shownBy, typeLabel, typeOf, who, words } from './logWords.ts'
import { ASSIGNED, COMPLETED, FOUND, FROM_ONE, LINES, RELEASED, TO_ALL, TO_ONE, TO_TWO } from './sample.ts'

const ZONE = 'America/Phoenix'

test('a message to one radio names it, and one from a radio names that radio', () => {
    expect(who(TO_ONE)).toBe('To Radio 4')
    expect(who(FROM_ONE)).toBe('From Radio 4')
})

test('a multicast names its radios, and a broadcast counts them', () => {
    expect(who(TO_TWO)).toBe('To Radios 1, 2')
    expect(who(TO_ALL)).toBe('Broadcast · 3 radios')
})

test('a broadcast that reached one radio counts one radio', () => {
    expect(who({ ...TO_ALL, radios: TO_ALL.radios.slice(0, 1) })).toBe('Broadcast · 1 radio')
})

test('a sector line names nobody: its words say the group', () => {
    expect(who(ASSIGNED)).toBe('')
    expect(words(ASSIGNED)).toBe('S1 assigned to Group 1')
    expect(words(COMPLETED)).toBe('S3 completed by Group 2')
})

test('a released line says when the sector is partial', () => {
    expect(words(RELEASED)).toBe('S4 released by Group 3 (partial)')
    expect(words({ ...RELEASED, partial: false })).toBe('S4 released by Group 3')
})

test("a message's words are its text", () => {
    expect(words(TO_ONE)).toBe('Radio 4: find a landing zone.')
})

test('a message to one radio says when it was acknowledged, in the mission time zone', () => {
    expect(acknowledged(TO_ONE, ZONE)).toBe('acknowledged 11:24 pm')
    expect(acknowledged({ ...TO_ONE, radios: [{ radio_id: 4, ack_time: null }] }, ZONE)).toBe('not acknowledged')
})

test('a message to several radios counts those that acknowledged', () => {
    expect(acknowledged(TO_TWO, ZONE)).toBe('1 acknowledged')
    expect(acknowledged(TO_ALL, ZONE)).toBe('3 acknowledged')
})

test('a message from a radio and a sector line have no acknowledgement', () => {
    expect(acknowledged(FROM_ONE, ZONE)).toBe('')
    expect(acknowledged(ASSIGNED, ZONE)).toBe('')
})

test('only a send to several radios opens', () => {
    expect(LINES.filter(opens)).toEqual([TO_TWO, TO_ALL])
})

test('a sector line is of the assignment type', () => {
    expect(typeOf(ASSIGNED)).toBe('assignment')
    expect(typeOf(FOUND)).toBe('found')
})

test('there are five type filters after All', () => {
    expect(FILTERS.map((filter) => filter.label)).toEqual(['All', 'Evidence', 'Found', 'Instruction', 'Out of sector', 'Assignment'])
})

test('a type has a label, and a type not on the list is shown by its code', () => {
    expect(typeLabel('out_of_sector')).toBe('Out of sector')
    expect(typeLabel('weather')).toBe('weather')
})

test('All shows every line, and a type shows only its own', () => {
    expect(shownBy(LINES, 'all')).toEqual(LINES)
    expect(shownBy(LINES, 'assignment')).toEqual([ASSIGNED, COMPLETED, RELEASED])
    expect(shownBy(LINES, 'evidence')).toEqual([FROM_ONE])
    expect(shownBy(LINES, 'out_of_sector')).toEqual([])
})
