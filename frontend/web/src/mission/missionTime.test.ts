import { expect, test } from 'vitest'
import { dayNumber, formatDateTime, formatElapsed, formatTime, listedZoneFor, TIME_ZONES, zoneLabel } from './missionTime.ts'

// Arizona07's first session: 8:30 pm on April 13 to 4:20 am on April 14, 2025, Arizona time.
const START = '2025-04-14T03:30:00Z'
const END = '2025-04-14T11:20:00Z'

test('a time is shown in the mission zone, on a 12-hour clock', () => {
    expect(formatTime(START, 'America/Phoenix')).toBe('8:30 pm')
    expect(formatTime(END, 'America/Phoenix')).toBe('4:20 am')
    // The same moment in Denver, which is an hour ahead of Arizona in April.
    expect(formatTime(START, 'America/Denver')).toBe('9:30 pm')
})

test('midnight and noon are written with 12', () => {
    expect(formatTime('2025-04-14T07:00:00Z', 'America/Phoenix')).toBe('12:00 am')
    expect(formatTime('2025-04-14T19:00:00Z', 'America/Phoenix')).toBe('12:00 pm')
})

test('a date and time is shown with the date as it is in the mission zone', () => {
    // April 14 in UTC is still April 13 in Arizona.
    expect(formatDateTime(START, 'America/Phoenix')).toBe('Apr 13, 2025, 8:30 pm')
    expect(formatDateTime(END, 'America/Phoenix')).toBe('Apr 14, 2025, 4:20 am')
})

test('the day number counts the dates sessions started on, in the mission zone', () => {
    const AFTER_MIDNIGHT = '2025-04-14T07:30:00Z'  // 12:30 am on April 14 in Arizona
    expect(dayNumber([START], 'America/Phoenix')).toBe(1)
    // A second session on the same date is still day 1.
    expect(dayNumber([START, '2025-04-14T05:00:00Z'], 'America/Phoenix')).toBe(1)
    // A session started at 12:30 am the same night is on the next date, so it is day 2.
    expect(dayNumber([START, AFTER_MIDNIGHT], 'America/Phoenix')).toBe(2)
    // In UTC both of those are April 14: the zone decides.
    expect(dayNumber([START, AFTER_MIDNIGHT], 'UTC')).toBe(1)
    // A session on a later date is the next day, however many dates were skipped.
    expect(dayNumber([START, '2026-11-24T23:00:00Z'], 'America/Phoenix')).toBe(2)
    expect(dayNumber([START, AFTER_MIDNIGHT, '2026-11-24T23:00:00Z'], 'America/Phoenix')).toBe(3)
})

test('elapsed time is hours, minutes and seconds', () => {
    const MINUTE = 60_000
    expect(formatElapsed(0)).toBe('0:00:00')
    expect(formatElapsed(30 * MINUTE + 5000)).toBe('0:30:05')
    expect(formatElapsed(470 * MINUTE)).toBe('7:50:00')
    expect(formatElapsed(26 * 60 * MINUTE)).toBe('26:00:00')
    expect(formatElapsed(-5000)).toBe('0:00:00')  // a clock set wrong never shows a minus
})

test('the list offers the seven US zones by plain name', () => {
    expect(TIME_ZONES.map((zone) => zone.label)).toEqual(
        ['Eastern', 'Central', 'Mountain', 'Arizona', 'Pacific', 'Alaska', 'Hawaii'])
    expect(zoneLabel('America/Phoenix')).toBe('Arizona')
    expect(zoneLabel('Europe/Paris')).toBe('Europe/Paris')  // not on the list: its own name
})

test('the laptop zone is matched to the listed zone that keeps the same time', () => {
    expect(listedZoneFor('America/Denver')).toBe('America/Denver')
    expect(listedZoneFor('America/Boise')).toBe('America/Denver')      // Mountain, with daylight time
    expect(listedZoneFor('America/Phoenix')).toBe('America/Phoenix')
    expect(listedZoneFor('America/Detroit')).toBe('America/New_York')
    expect(listedZoneFor('Europe/Paris')).toBe('America/New_York')     // no match: the first on the list
})
