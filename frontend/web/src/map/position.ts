import type { Position } from './geo.ts'

// The one place that writes a position on screen: decimal degrees with a letter, to four
// places (about 11 m), as "31.5063 N 110.6775 W". Every position goes through here, so
// another way of writing them, such as a grid reference, is a change to this file only.

export function formatPosition(position: Position): string {
    return `${formatLatitude(position.lat)} ${formatLongitude(position.lon)}`
}

export function formatLatitude(degrees: number): string {
    return `${Math.abs(degrees).toFixed(4)} ${degrees < 0 ? 'S' : 'N'}`
}

export function formatLongitude(degrees: number): string {
    return `${Math.abs(degrees).toFixed(4)} ${degrees < 0 ? 'W' : 'E'}`
}

// A bearing from true north as three digits, "047°".
export function formatBearing(degrees: number): string {
    return `${String(Math.round(degrees) % 360).padStart(3, '0')}°`
}
