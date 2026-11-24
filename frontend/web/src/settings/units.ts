import type { Units } from './settings.ts'

// The one place that turns a saved number into the text shown on screen. Numbers are saved
// in meters and square meters, and are converted only here, so changing the Units setting
// changes every number together.

export const METERS_PER_FOOT = 0.3048
export const METERS_PER_MILE = 1609.344

// A distance: feet or meters while short, miles or kilometers with one decimal from 1,000
// feet or 1,000 meters. The switch is made on the rounded number, so "1,000 ft" is never shown.
export function formatDistance(meters: number, units: Units): string {
    if (units === 'imperial') {
        const feet = meters / METERS_PER_FOOT
        return Math.round(feet) < 1000 ? `${rounded(feet, 0)} ft` : `${rounded(meters / METERS_PER_MILE, 1)} mi`
    }
    return Math.round(meters) < 1000 ? `${rounded(meters, 0)} m` : `${rounded(meters / 1000, 1)} km`
}

// An area: square miles or square kilometers, with two decimals.
export function formatArea(squareMeters: number, units: Units): string {
    if (units === 'imperial') return `${rounded(squareMeters / METERS_PER_MILE ** 2, 2)} mi²`
    return `${rounded(squareMeters / 1000 ** 2, 2)} km²`
}

// An elevation: whole feet or whole meters.
export function formatElevation(meters: number, units: Units): string {
    if (units === 'imperial') return `${rounded(meters / METERS_PER_FOOT, 0)} ft`
    return `${rounded(meters, 0)} m`
}

// The number as text with exactly this many decimals, and a comma between thousands.
function rounded(n: number, decimals: number): string {
    return n.toLocaleString('en-US', { minimumFractionDigits: decimals, maximumFractionDigits: decimals })
}
