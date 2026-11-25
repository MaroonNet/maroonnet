import { expect, test } from 'vitest'
import { kindOf, KINDS } from './kinds.ts'
import { ARIZONA07, waypoint } from './sample.ts'
import { bytes, commandPost, startingName } from './waypointWords.ts'

test('there are ten kinds, each with its plain name', () => {
    expect(KINDS.map((kind) => kind.label)).toEqual([
        'Command post', 'Last known position', 'Point last seen', 'Evidence', 'Hazard', 'Landing zone', 'Find',
        'Relay', 'Meeting point', 'Other',
    ])
})

test('yellow, orange and white markers take a dark icon, and the rest a light one', () => {
    expect(KINDS.filter((kind) => kind.darkIcon).map((kind) => kind.code)).toEqual(['hazard', 'relay', 'other'])
})

test('a kind the app does not know is shown as Other is, under its own word', () => {
    const unknown = kindOf('campsite')
    expect(unknown.label).toBe('campsite')
    expect(unknown.icon).toBe(kindOf('other').icon)
})

test('a letter counts as one byte and an accented letter as two', () => {
    expect(bytes('Canon')).toBe(5)
    expect(bytes('Cañon')).toBe(6)
})

test('a new waypoint starts named for its kind, numbered after those on the map', () => {
    expect(startingName('hazard', ARIZONA07)).toBe('Hazard 1')
    expect(startingName('find', ARIZONA07)).toBe('Find 3')
    expect(startingName('find', [waypoint(1, 'find', 'Find 2')])).toBe('Find 3')  // a name on the map is not given again
})

test('there is one command post, so its name has no number', () => {
    expect(startingName('command_post', ARIZONA07)).toBe('Command post')
})

test('the command post is the command post waypoint, if there is one', () => {
    expect(commandPost(ARIZONA07)?.id).toBe(1)
    expect(commandPost([waypoint(2, 'hazard', 'Mine shaft')])).toBeUndefined()
})
