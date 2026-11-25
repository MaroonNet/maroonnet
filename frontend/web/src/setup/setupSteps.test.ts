import { expect, test } from 'vitest'
import { ARIZONA, ARIZONA07_AREA, ARIZONA07_PACK, pack } from './sample.ts'
import { covers, setupSteps, type SetupFacts } from './setupSteps.ts'

// A mission just created: nothing drawn, nothing placed, nobody checked in.
const NEW: SetupFacts = { area: null, packs: ARIZONA, hasPost: false, checkedIn: 0 }

const step = (facts: SetupFacts, id: string) => setupSteps(facts).find((one) => one.id === id)!

// Whether boxes cover a rectangle

test('a rectangle inside one box is covered', () => {
    expect(covers(ARIZONA07_AREA, [[-114.82, 31.33, -109.04, 37.01]])).toBe(true)
})

test('a rectangle that reaches past the box is not covered', () => {
    expect(covers({ ...ARIZONA07_AREA, min_lon: -115 }, [[-114.82, 31.33, -109.04, 37.01]])).toBe(false)
})

test('two boxes side by side cover a rectangle that lies across their shared edge', () => {
    const area = { min_lat: 36.5, min_lon: -109.5, max_lat: 36.9, max_lon: -108.5 }
    expect(covers(area, [[-114.82, 31.33, -109.04, 37.01], [-109.04, 31.33, -103.0, 37.01]])).toBe(true)
})

test('two boxes with a gap between them do not', () => {
    const area = { min_lat: 36.5, min_lon: -109.5, max_lat: 36.9, max_lon: -108.5 }
    expect(covers(area, [[-114.82, 31.33, -109.04, 37.01], [-109.0, 31.33, -103.0, 37.01]])).toBe(false)
})

test('no boxes cover nothing', () => {
    expect(covers(ARIZONA07_AREA, [])).toBe(false)
})

// The four steps

test('a new mission has four steps, none done, and says what each still needs', () => {
    expect(setupSteps(NEW)).toEqual([
        { id: 'area', label: 'Search Area', done: false, red: false, missing: ['No search area.'] },
        { id: 'maps', label: 'Offline Maps', done: false, red: false, missing: [] },  // nothing to check yet
        { id: 'post', label: 'Mark CP', done: false, red: false, missing: ['Command post not placed.'] },
        { id: 'people', label: 'Check In People', done: false, red: false, missing: ['Nobody is checked in.'] },
    ])
})

test('each of the three steps is done from its own fact, whatever the others say', () => {
    expect(step({ ...NEW, area: ARIZONA07_AREA }, 'area')).toMatchObject({ done: true, missing: [] })
    expect(step({ ...NEW, hasPost: true }, 'post')).toMatchObject({ done: true, missing: [] })
    expect(step({ ...NEW, checkedIn: 1 }, 'people')).toMatchObject({ done: true, missing: [] })
    expect(setupSteps({ ...NEW, hasPost: true }).filter((one) => one.done).map((one) => one.id)).toEqual(['post'])
})

// The Offline Maps step

test('the maps step is done when a state pack and a mission pack both cover the search area', () => {
    expect(step({ ...NEW, area: ARIZONA07_AREA, packs: [...ARIZONA, ARIZONA07_PACK] }, 'maps')).toEqual(
        { id: 'maps', label: 'Offline Maps', done: true, red: false, missing: [] })
})

test('with the state pack only, the step is red and says the mission pack is missing', () => {
    expect(step({ ...NEW, area: ARIZONA07_AREA, packs: ARIZONA }, 'maps')).toMatchObject(
        { done: false, red: true, missing: ['No mission pack covers the search area.'] })
})

test('a state pack is its basemap and its terrain: with one of them missing, no state pack covers the area', () => {
    const basemapOnly = [ARIZONA[0], ARIZONA07_PACK]
    expect(step({ ...NEW, area: ARIZONA07_AREA, packs: basemapOnly }, 'maps')).toMatchObject(
        { done: false, red: true, missing: ['No state pack covers the search area.'] })
})

test('with nothing over the area, the step says no maps are installed for it', () => {
    const colorado = [pack('state/CO/basemap', [[-109.06, 36.99, -102.04, 41.0]]), pack('state/CO/terrain', [[-109.06, 36.99, -102.04, 41.0]])]
    expect(step({ ...NEW, area: ARIZONA07_AREA, packs: colorado }, 'maps')).toMatchObject(
        { done: false, red: true, missing: ['No maps are installed for this area.'] })
})

test('a partial pack does not count', () => {
    const partial = { ...ARIZONA07_PACK, status: 'partial' as const }
    expect(step({ ...NEW, area: ARIZONA07_AREA, packs: [...ARIZONA, partial] }, 'maps')).toMatchObject(
        { done: false, red: true, missing: ['No mission pack covers the search area.'] })
})

test('a search area partly outside the mission pack is not covered by it', () => {
    const wider = { ...ARIZONA07_AREA, max_lon: -110.3 }
    expect(step({ ...NEW, area: wider, packs: [...ARIZONA, ARIZONA07_PACK] }, 'maps')).toMatchObject(
        { done: false, red: true, missing: ['No mission pack covers the search area.'] })
})

test('while the packs are being read the step is neither done nor red', () => {
    expect(step({ ...NEW, area: ARIZONA07_AREA, packs: 'reading' }, 'maps')).toMatchObject({ done: false, red: false, missing: [] })
})

test('if the packs could not be read the step is red and says so', () => {
    expect(step({ ...NEW, area: ARIZONA07_AREA, packs: 'failed' }, 'maps')).toMatchObject(
        { done: false, red: true, missing: ['The installed maps could not be read.'] })
})
