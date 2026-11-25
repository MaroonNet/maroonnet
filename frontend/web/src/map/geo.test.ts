import { expect, test } from 'vitest'
import { bearingDegrees, distanceMeters, rectangleSize } from './geo.ts'
import { formatBearing, formatLatitude, formatLongitude, formatPosition } from './position.ts'

test('one degree of latitude is 111.2 km', () => {
    expect(distanceMeters({ lat: 0, lon: 0 }, { lat: 1, lon: 0 })).toBeCloseTo(111_195, 0)
})

test('Los Angeles airport to New York JFK is 3,974 km, setting off at 66 degrees', () => {
    // Two airports whose distance and first bearing are widely published.
    const lax = { lat: 33.9425, lon: -118.4081 }
    const jfk = { lat: 40.6413, lon: -73.7781 }
    expect(distanceMeters(lax, jfk) / 1000).toBeCloseTo(3974, 0)
    expect(bearingDegrees(lax, jfk)).toBeCloseTo(66, 0)
})

test('a bearing is counted clockwise from true north, 0 up to 360', () => {
    const here = { lat: 31.5, lon: -110.7 }
    expect(bearingDegrees(here, { lat: 31.6, lon: -110.7 })).toBeCloseTo(0, 1)    // north
    expect(bearingDegrees(here, { lat: 31.5, lon: -110.6 })).toBeCloseTo(90, 1)   // east
    expect(bearingDegrees(here, { lat: 31.4, lon: -110.7 })).toBeCloseTo(180, 1)  // south
    expect(bearingDegrees(here, { lat: 31.5, lon: -110.8 })).toBeCloseTo(270, 1)  // west
})

test("Arizona07's search area is 25.1 by 25.2 km", () => {
    const size = rectangleSize({ min_lat: 31.3926, min_lon: -110.8083, max_lat: 31.619, max_lon: -110.544 })
    expect(size.width / 1000).toBeCloseTo(25.1, 1)
    expect(size.height / 1000).toBeCloseTo(25.2, 1)
    expect(size.area / 1_000_000).toBeCloseTo(630.8, 1)  // square kilometers
})

test('a position is written in decimal degrees with letters, to four places', () => {
    expect(formatPosition({ lat: 31.5063, lon: -110.6775 })).toBe('31.5063 N 110.6775 W')
    expect(formatPosition({ lat: -33.86, lon: 151.2094 })).toBe('33.8600 S 151.2094 E')
})

test('a latitude or a longitude alone is written the same way', () => {
    expect(formatLatitude(31.619)).toBe('31.6190 N')
    expect(formatLongitude(-110.544)).toBe('110.5440 W')
    expect(formatLatitude(0)).toBe('0.0000 N')
    expect(formatLongitude(0)).toBe('0.0000 E')
})

test('a bearing is written as three digits', () => {
    expect(formatBearing(47.4)).toBe('047°')
    expect(formatBearing(270)).toBe('270°')
    expect(formatBearing(359.7)).toBe('000°')  // rounds up to north, never "360°"
})
