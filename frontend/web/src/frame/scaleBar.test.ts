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
    expect(scaleBar(MILE / 100, 170, 'imperial')).toEqual({ label: '1 mi', width: 100 })
    // 10 pixels to the mile: 17 miles fit, so 10 miles.
    expect(scaleBar(MILE / 10, 170, 'imperial')).toEqual({ label: '10 mi', width: 100 })
    // 50 pixels to the mile: 3.4 miles fit, so 3 miles.
    expect(scaleBar(MILE / 50, 170, 'imperial')).toEqual({ label: '3 mi', width: 150 })
})

test('half a mile is the shortest distance shown in miles', () => {
    // 0.8 of a mile fits in 170 pixels, so the bar is half a mile: 170 x 0.5 / 0.8 pixels.
    expect(scaleBar(0.8 * MILE / 170, 170, 'imperial')).toEqual({ label: '0.5 mi', width: 106 })
})

test('under half a mile the bar is in feet', () => {
    // 1 pixel to the foot: 170 feet fit, so 100 feet.
    expect(scaleBar(FOOT, 170, 'imperial')).toEqual({ label: '100 ft', width: 100 })
    // 10 feet to the pixel: 1,700 feet fit (0.32 of a mile), so 1,000 feet.
    expect(scaleBar(10 * FOOT, 170, 'imperial')).toEqual({ label: '1,000 ft', width: 100 })
})

test('under the metric choice the bar is in kilometers from 1 km, and in meters below that', () => {
    // 10 meters to the pixel: 1,700 meters fit, so 1 kilometer, 100 pixels wide.
    expect(scaleBar(10, 170, 'metric')).toEqual({ label: '1 km', width: 100 })
    // 100 meters to the pixel: 17 kilometers fit, so 10 kilometers.
    expect(scaleBar(100, 170, 'metric')).toEqual({ label: '10 km', width: 100 })
    // 5 meters to the pixel: 850 meters fit, so 500 meters.
    expect(scaleBar(5, 170, 'metric')).toEqual({ label: '500 m', width: 100 })
    // 1 meter to the pixel: 170 meters fit, so 100 meters.
    expect(scaleBar(1, 170, 'metric')).toEqual({ label: '100 m', width: 100 })
})
