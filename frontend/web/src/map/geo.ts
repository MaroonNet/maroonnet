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

// A shape's area on the ground, in square meters. The corners go in order, either way round,
// and the last joins back to the first. Each corner adds a strip reaching from it down to
// the equator; the strips outside the shape cancel out (the method mapping libraries such
// as Turf use).
export function polygonArea(corners: Position[]): number {
    let sum = 0
    for (let i = 0; i < corners.length; i++) {
        const before = corners[(i + corners.length - 1) % corners.length]
        const after = corners[(i + 1) % corners.length]
        sum += radians(after.lon - before.lon) * Math.sin(radians(corners[i].lat))
    }
    return Math.abs(sum) * EARTH_RADIUS ** 2 / 2
}

// The middle of a shape's ground (its centroid), where its label goes. Each side, with the
// first corner, makes a triangle; the middles of the triangles are averaged, each counting
// by its area. Degrees are treated as a flat grid, which is close enough at a sector's size.
export function polygonCenter(corners: Position[]): Position {
    const first = corners[0]
    let area = 0, lat = 0, lon = 0
    for (let i = 1; i < corners.length - 1; i++) {
        const b = corners[i], c = corners[i + 1]
        const piece = ((b.lat - first.lat) * (c.lon - first.lon) - (b.lon - first.lon) * (c.lat - first.lat)) / 2
        area += piece
        lat += piece * (first.lat + b.lat + c.lat) / 3
        lon += piece * (first.lon + b.lon + c.lon) / 3
    }
    return area === 0 ? first : { lat: lat / area, lon: lon / area }
}

// The place itself when it is inside the rectangle or on its line, and otherwise the nearest
// place on the line.
export function onOrInside(place: Position, box: Bounds): Position {
    return {
        lat: Math.min(Math.max(place.lat, box.min_lat), box.max_lat),
        lon: Math.min(Math.max(place.lon, box.min_lon), box.max_lon),
    }
}

// Whether every corner is inside the rectangle. A corner on its line counts as inside, as
// the backend counts it (backend/sectors/shape.py).
export function insideBounds(corners: Position[], box: Bounds): boolean {
    return corners.every(({ lat, lon }) => box.min_lat <= lat && lat <= box.max_lat && box.min_lon <= lon && lon <= box.max_lon)
}
