import type { Units } from '../settings/settings.ts'
import { METERS_PER_FOOT, METERS_PER_MILE } from '../settings/units.ts'

// The sums behind the scale bar: how much ground a pixel covers, and which round distance
// to draw.

const EQUATOR = 40075016.686  // meters around the Earth at the equator
const TILE = 512              // pixels across the whole world at zoom 0

// How many meters of ground one screen pixel covers. Each zoom halves it, and it shrinks
// away from the equator as the map stretches the ground sideways.
export function metersPerPixel(latitude: number, zoom: number): number {
    return EQUATOR * Math.cos(latitude * Math.PI / 180) / (TILE * 2 ** zoom)
}

// The two units each choice draws the bar in. The large one is used once at least `from` of
// it fits in the bar: miles from half a mile, kilometers from one kilometer.
const BAR_UNITS = {
    imperial: { large: 'mi', largeMeters: METERS_PER_MILE, from: 0.5, small: 'ft', smallMeters: METERS_PER_FOOT },
    metric: { large: 'km', largeMeters: 1000, from: 1, small: 'm', smallMeters: 1 },
}

// The longest round distance that fits in maxWidth pixels, and how many pixels wide it is.
export function scaleBar(metersPerPixel: number, maxWidth: number, units: Units): { label: string, width: number } {
    const { large, largeMeters, from, small, smallMeters } = BAR_UNITS[units]
    const meters = metersPerPixel * maxWidth  // the ground the widest bar would cover
    const inLarge = meters / largeMeters

    if (inLarge >= from) {
        const round = inLarge < 1 ? from : roundDown(inLarge)  // between a half and one mile: half a mile
        return { label: `${round.toLocaleString('en-US')} ${large}`, width: Math.round(maxWidth * round / inLarge) }
    }
    const inSmall = meters / smallMeters
    const round = roundDown(inSmall)
    return { label: `${round.toLocaleString('en-US')} ${small}`, width: Math.round(maxWidth * round / inSmall) }
}

// The largest of 1, 2, 3 or 5 times a power of ten that is not above the number: 170 gives
// 100, 3.4 gives 3, 1700 gives 1000.
function roundDown(n: number): number {
    const power = 10 ** Math.floor(Math.log10(n))
    const lead = n / power  // from 1 up to 10
    return (lead >= 5 ? 5 : lead >= 3 ? 3 : lead >= 2 ? 2 : 1) * power
}
