import { expect, test } from 'vitest'
import { formatArea, formatDistance, formatElevation } from './units.ts'

// Every number is handed over in meters or square meters, as it is saved.
const FOOT = 0.3048            // meters
const MILE = 1609.344          // meters
const SQUARE_MILE = MILE * MILE

test('a short distance is in whole feet, or whole meters', () => {
    expect(formatDistance(850 * FOOT, 'imperial')).toBe('850 ft')
    expect(formatDistance(850, 'metric')).toBe('850 m')
})

test('from 1,000 feet a distance is in miles with one decimal', () => {
    expect(formatDistance(1000 * FOOT, 'imperial')).toBe('0.2 mi')
    expect(formatDistance(1.2 * MILE, 'imperial')).toBe('1.2 mi')
    expect(formatDistance(1234.5 * MILE, 'imperial')).toBe('1,234.5 mi')
})

test('from 1,000 meters a distance is in kilometers with one decimal', () => {
    expect(formatDistance(1000, 'metric')).toBe('1.0 km')
    expect(formatDistance(1200, 'metric')).toBe('1.2 km')
})

test('a distance that rounds up to 1,000 is written in the larger unit, never as "1,000 ft"', () => {
    expect(formatDistance(999.6 * FOOT, 'imperial')).toBe('0.2 mi')
    expect(formatDistance(999.6, 'metric')).toBe('1.0 km')
})

test('an area is in square miles or square kilometers, with two decimals', () => {
    expect(formatArea(0.06 * SQUARE_MILE, 'imperial')).toBe('0.06 mi²')
    expect(formatArea(2 * SQUARE_MILE, 'imperial')).toBe('2.00 mi²')
    expect(formatArea(160_000, 'metric')).toBe('0.16 km²')
    expect(formatArea(5_180_000, 'metric')).toBe('5.18 km²')
})

test('an elevation is in whole feet or whole meters', () => {
    expect(formatElevation(5393 * FOOT, 'imperial')).toBe('5,393 ft')
    expect(formatElevation(5393 * FOOT, 'metric')).toBe('1,644 m')
})
