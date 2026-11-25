// Distances and directions on the ground. The earth is treated as a ball of one radius,
// which is right to about 0.3 percent: 3 m in a kilometer.

// A place, in degrees. South and west are negative.
export type Position = { lat: number, lon: number }

// A rectangle on the map, as the backend saves one: its south-west and north-east corners.
export type Bounds = {
    min_lat: number
    min_lon: number
    max_lat: number
    max_lon: number
}

const EARTH_RADIUS = 6_371_008.8  // meters, the earth's mean radius

// The math functions take angles in radians, not degrees.
const radians = (degrees: number) => degrees * Math.PI / 180

// How far apart two places are, in meters, along the shortest path over the ground (the
// haversine formula).
export function distanceMeters(from: Position, to: Position): number {
    const lat1 = radians(from.lat), lat2 = radians(to.lat)
    const a = Math.sin((lat2 - lat1) / 2) ** 2
        + Math.cos(lat1) * Math.cos(lat2) * Math.sin(radians(to.lon - from.lon) / 2) ** 2
    return 2 * EARTH_RADIUS * Math.asin(Math.sqrt(a))
}

// The direction to set off in from one place to reach another: degrees clockwise from true
// north, from 0 up to 360.
export function bearingDegrees(from: Position, to: Position): number {
    const lat1 = radians(from.lat), lat2 = radians(to.lat), east = radians(to.lon - from.lon)
    const y = Math.sin(east) * Math.cos(lat2)
    const x = Math.cos(lat1) * Math.sin(lat2) - Math.sin(lat1) * Math.cos(lat2) * Math.cos(east)
    return (Math.atan2(y, x) * 180 / Math.PI + 360) % 360
}

// A rectangle's size on the ground: meters wide and high, and its area in square meters.
// Its top and bottom edges differ a little in length, because lines of longitude close in
// toward the poles, so the width is taken across its middle.
export function rectangleSize(box: Bounds): { width: number, height: number, area: number } {
    const east = radians(box.max_lon - box.min_lon)
    const middle = radians((box.min_lat + box.max_lat) / 2)
    return {
        width: EARTH_RADIUS * Math.cos(middle) * east,
        height: EARTH_RADIUS * radians(box.max_lat - box.min_lat),
        area: EARTH_RADIUS ** 2 * east * (Math.sin(radians(box.max_lat)) - Math.sin(radians(box.min_lat))),
    }
}
