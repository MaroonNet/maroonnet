import { expect, test } from 'vitest'
import { bearingDegrees, distanceMeters, insideBounds, onOrInside, polygonArea, rectangleSize } from './geo.ts'
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

const ARIZONA07_AREA = { min_lat: 31.3926, min_lon: -110.8083, max_lat: 31.619, max_lon: -110.544 }

test("a shape drawn as the search area's four corners has the search area's area", () => {
    const { min_lat: s, min_lon: w, max_lat: n, max_lon: e } = ARIZONA07_AREA
    const corners = [{ lat: s, lon: w }, { lat: n, lon: w }, { lat: n, lon: e }, { lat: s, lon: e }]
    expect(polygonArea(corners)).toBeCloseTo(rectangleSize(ARIZONA07_AREA).area, -3)
})

test('the corners may go either way round, and the area is the same', () => {
    const square = [{ lat: 31.5, lon: -110.7 }, { lat: 31.51, lon: -110.7 }, { lat: 31.51, lon: -110.69 }, { lat: 31.5, lon: -110.69 }]
    expect(polygonArea([...square].reverse())).toBeCloseTo(polygonArea(square), 3)
})

test("Arizona07's S7 is 0.55 square kilometers", () => {
    const s7 = [[31.510046, -110.679325], [31.513835, -110.679272], [31.515188, -110.676638], [31.515278, -110.672002],
        [31.513925, -110.668209], [31.510948, -110.667893], [31.509280, -110.671791], [31.510633, -110.675585], [31.510588, -110.677481]]
    // Worked out separately by laying the corners on a flat grid of meters: 0.553 km². A
    // shape this small is the same on the curved earth to well under a percent.
    expect(polygonArea(s7.map(([lat, lon]) => ({ lat, lon }))) / 1_000_000).toBeCloseTo(0.553, 2)
})

test('a point past the search area line is put on the line, at the nearest spot', () => {
    expect(onOrInside({ lat: 31.5, lon: -110.5 }, ARIZONA07_AREA)).toEqual({ lat: 31.5, lon: -110.544 })   // past the east line
    expect(onOrInside({ lat: 31.7, lon: -110.9 }, ARIZONA07_AREA)).toEqual({ lat: 31.619, lon: -110.8083 })  // past the north-west corner
    expect(onOrInside({ lat: 31.5, lon: -110.6 }, ARIZONA07_AREA)).toEqual({ lat: 31.5, lon: -110.6 })      // inside: unchanged
})

test('a shape is inside the search area when every corner is, the line included', () => {
    expect(insideBounds([{ lat: 31.3926, lon: -110.8083 }, { lat: 31.5, lon: -110.6 }], ARIZONA07_AREA)).toBe(true)
    expect(insideBounds([{ lat: 31.39, lon: -110.7 }, { lat: 31.5, lon: -110.6 }], ARIZONA07_AREA)).toBe(false)
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
