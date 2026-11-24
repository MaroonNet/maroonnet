import { expect, test } from 'vitest'
import { metersPerPixel, scaleBar } from './scaleBar.ts'

const MILE = 1609.344  // meters
const FOOT = 0.3048    // meters

test('one pixel covers 78,271.52 m of the equator at zoom 0, and half as much per zoom', () => {
    expect(metersPerPixel(0, 0)).toBeCloseTo(78271.52, 2)
    expect(metersPerPixel(0, 1)).toBeCloseTo(39135.76, 2)
})

test('one pixel covers half as much at 60 degrees north as at the equator', () => {
    expect(metersPerPixel(60, 0)).toBeCloseTo(39135.76, 2)
})

test('the bar shows the longest round distance that fits, and is drawn that wide', () => {
    // 100 pixels to the mile: 1.7 miles fit in 170 pixels, so the bar is 1 mile, 100 pixels wide.
    expect(scaleBar(MILE / 100, 170)).toEqual({ label: '1 mi', width: 100 })
    // 10 pixels to the mile: 17 miles fit, so 10 miles.
    expect(scaleBar(MILE / 10, 170)).toEqual({ label: '10 mi', width: 100 })
    // 50 pixels to the mile: 3.4 miles fit, so 3 miles.
    expect(scaleBar(MILE / 50, 170)).toEqual({ label: '3 mi', width: 150 })
})

test('half a mile is the shortest distance shown in miles', () => {
    // 0.8 of a mile fits in 170 pixels, so the bar is half a mile: 170 x 0.5 / 0.8 pixels.
    expect(scaleBar(0.8 * MILE / 170, 170)).toEqual({ label: '0.5 mi', width: 106 })
})

test('under half a mile the bar is in feet', () => {
    // 1 pixel to the foot: 170 feet fit, so 100 feet.
    expect(scaleBar(FOOT, 170)).toEqual({ label: '100 ft', width: 100 })
    // 10 feet to the pixel: 1,700 feet fit (0.32 of a mile), so 1,000 feet.
    expect(scaleBar(10 * FOOT, 170)).toEqual({ label: '1,000 ft', width: 100 })
})
