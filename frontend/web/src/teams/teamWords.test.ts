import { expect, test } from 'vitest'
import { GROUPS, PEOPLE, RADIOS } from './sample.ts'
import { carriedBy, freePeople, freeRadios, GROUP_COLORS, groupColor, groupLine, lastPosition, teamsOf } from './teamWords.ts'

const radio = (id: number) => RADIOS.find((r) => r.id === id)!

test('there are seven group colors, used in order and again after the seventh', () => {
    expect(new Set(GROUP_COLORS).size).toBe(7)
    expect(groupColor(1)).toBe(GROUP_COLORS[0])
    expect(groupColor(7)).toBe(GROUP_COLORS[6])
    expect(groupColor(8)).toBe(GROUP_COLORS[0])
})

test('each group color is written as the map reads a color, and none is a sector status color', () => {
    for (const color of GROUP_COLORS) expect(color).toMatch(/^#[0-9a-f]{6}$/)
    for (const taken of ['#c9302d', '#e57600', '#218a45']) expect(GROUP_COLORS).not.toContain(taken)
})

test('a team is a searcher radio with someone on it', () => {
    // Radio 5 has nobody, radio 6 is a relay and radio 8 is the command post's.
    expect(teamsOf(RADIOS).map((r) => r.id)).toEqual([1, 2, 4, 7])
})

test('a radio that can be made a team is a searcher radio with nobody on it', () => {
    expect(freeRadios(RADIOS).map((r) => r.id)).toEqual([5])
})

test('the people who can join a team are checked in and carry no radio', () => {
    expect(freePeople(PEOPLE).map((p) => p.last_name)).toEqual(['Feld', '#1'])
})

test('a radio reads who carries it', () => {
    expect(carriedBy(radio(1))).toBe('Marcus Ibarra, Tessa Lindqvist')
    expect(carriedBy(radio(1), 1)).toBe('Marcus Ibarra +1')
    expect(carriedBy(radio(5))).toBe('Nobody')
})

test('a radio reads the time of its newest position in the mission\'s zone', () => {
    expect(lastPosition(radio(1), 'America/Phoenix')).toBe('Last position 4:19 am')
    expect(lastPosition(radio(4), 'America/Phoenix')).toBe('No position yet')
})

test('a group reads its sector, or that it has no teams', () => {
    expect(GROUPS.map(groupLine)).toEqual(['Group 1 · S4', 'Group 2', 'Group 3 · no teams'])
})
