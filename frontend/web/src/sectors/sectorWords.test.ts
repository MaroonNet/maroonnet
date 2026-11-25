import { expect, test } from 'vitest'
import { lookOf, mapLabel, sectorColor, SECTOR_COLORS } from './looks.ts'
import { held, sector } from './sample.ts'
import { sectorLine, sendsLine, standingOf, statusLabel } from './sectorWords.ts'
import { groupColor } from '../teams/teamWords.ts'

const ZONE = 'America/Phoenix'

test('a drawn sector a group holds reads Assigned; so does a partial one given out again', () => {
    expect(statusLabel(sector(7, 'drawn'))).toBe('Drawn')
    expect(statusLabel(held(7, 'drawn', 3))).toBe('Assigned')
    expect(statusLabel(sector(4, 'partial'))).toBe('Partial')
    expect(statusLabel(held(4, 'partial', 3))).toBe('Assigned')
    expect(statusLabel(held(4, 'searching', 3))).toBe('Searching')
    expect(statusLabel(sector(1, 'completed'))).toBe('Completed')
    expect(standingOf(held(4, 'partial', 3))).toBe('assigned')
})

test("the panel's line names the group that holds a sector", () => {
    expect(sectorLine(sector(7, 'drawn'), ZONE)).toBe('Unassigned')
    expect(sectorLine(held(7, 'drawn', 3), ZONE)).toBe('Assigned to Group 3')
    expect(sectorLine(held(4, 'searching', 3), ZONE)).toBe('Being searched by Group 3')
    expect(sectorLine(sector(4, 'partial'), ZONE)).toBe('Searched in part')
    expect(sectorLine(sector(1, 'completed'), ZONE)).toBe('Completed 1:21 am')
})

test('the five looks: an assigned sector is red, a searching one its group\'s color', () => {
    expect(lookOf(sector(7, 'drawn'))).toBe('drawn')
    expect(lookOf(held(7, 'drawn', 3))).toBe('assigned')
    expect(lookOf(held(4, 'searching', 3))).toBe('searching')
    expect(lookOf(sector(1, 'completed'))).toBe('completed')
    expect(sectorColor(held(7, 'drawn', 3))).toBe(SECTOR_COLORS.drawn)
    expect(sectorColor(held(4, 'searching', 3))).toBe(groupColor(3))
})

test('a partial sector given out again keeps its stripes until a team enters it', () => {
    expect(lookOf(held(4, 'partial', 3))).toBe('partial')
    expect(sectorColor(held(4, 'partial', 3))).toBe(SECTOR_COLORS.partial)
})

test('on the map a sector a group holds is labeled with the group', () => {
    expect(mapLabel(sector(7, 'drawn'))).toBe('S7')
    expect(mapLabel(held(4, 'partial', 3))).toBe('S4 → G3')
    expect(mapLabel(held(4, 'searching', 3))).toBe('S4 → G3')
})

const send = (radio_id: number, acknowledged = true) => ({
    radio_id, sent_time: '2025-04-14T03:50:55Z', ack_time: acknowledged ? '2025-04-14T03:51:08Z' : null,
})

test('the saved sends of a sector read as one line', () => {
    expect(sendsLine([])).toBeNull()
    expect(sendsLine([send(1), send(2), send(3)])).toBe('Sent to Radios 1, 2, 3 · all acknowledged')
    expect(sendsLine([send(7)])).toBe('Sent to Radio 7 · acknowledged')
    expect(sendsLine([send(7, false)])).toBe('Sent to Radio 7 · not acknowledged')
    expect(sendsLine([send(1), send(2, false), send(3)])).toBe('Sent to Radios 1, 2, 3 · 2 of 3 acknowledged')
    expect(sendsLine([send(1, false), send(2, false)])).toBe('Sent to Radios 1, 2 · none acknowledged')
})

test('a sector sent to a radio twice counts that radio once, by its newest send', () => {
    const first = { radio_id: 1, sent_time: '2025-04-14T03:50:55Z', ack_time: null }
    const again = { radio_id: 1, sent_time: '2025-04-14T03:55:00Z', ack_time: '2025-04-14T03:55:09Z' }
    expect(sendsLine([first, again])).toBe('Sent to Radio 1 · acknowledged')
})
