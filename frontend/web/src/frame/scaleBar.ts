// The sums behind the scale bar: how much ground a pixel covers, and which round distance
// to draw.

const EQUATOR = 40075016.686  // meters around the Earth at the equator
const TILE = 512              // pixels across the whole world at zoom 0
const MILE = 1609.344         // meters
const FOOT = 0.3048           // meters

// How many meters of ground one screen pixel covers. Each zoom halves it, and it shrinks
// away from the equator as the map stretches the ground sideways.
export function metersPerPixel(latitude: number, zoom: number): number {
    return EQUATOR * Math.cos(latitude * Math.PI / 180) / (TILE * 2 ** zoom)
}

// The longest round distance that fits in maxWidth pixels, and how many pixels wide it is.
// Miles from half a mile up, feet below that.
export function scaleBar(metersPerPixel: number, maxWidth: number): { label: string, width: number } {
    const miles = metersPerPixel * maxWidth / MILE
    if (miles >= 0.5) {
        const round = miles < 1 ? 0.5 : roundDown(miles)
        return { label: `${round.toLocaleString('en-US')} mi`, width: Math.round(maxWidth * round / miles) }
    }
    const feet = metersPerPixel * maxWidth / FOOT
    const round = roundDown(feet)
    return { label: `${round.toLocaleString('en-US')} ft`, width: Math.round(maxWidth * round / feet) }
}

// The largest of 1, 2, 3 or 5 times a power of ten that is not above the number: 170 gives
// 100, 3.4 gives 3, 1700 gives 1000.
function roundDown(n: number): number {
    const power = 10 ** Math.floor(Math.log10(n))
    const lead = n / power  // from 1 up to 10
    return (lead >= 5 ? 5 : lead >= 3 ? 3 : lead >= 2 ? 2 : 1) * power
}
