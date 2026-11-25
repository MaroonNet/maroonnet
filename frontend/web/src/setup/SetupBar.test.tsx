import { cleanup, render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import { MissionContext, type MissionStatus } from '../mission/mission.ts'
import { PeopleContext } from '../people/people.ts'
import { SearchAreaContext, type SearchArea } from '../searchArea/searchArea.ts'
import { arizona, PEOPLE } from '../teams/sample.ts'
import { ARIZONA07 as WAYPOINTS, board } from '../waypoints/sample.ts'
import { WaypointsContext, type Waypoint } from '../waypoints/waypoints.ts'
import type { InstalledPack } from './packs.ts'
import { ARIZONA, ARIZONA07_AREA, ARIZONA07_PACK } from './sample.ts'
import SetupBar from './SetupBar.tsx'

afterEach(() => {
    cleanup()
    vi.unstubAllGlobals()
})

type Shown = { status?: MissionStatus | null, area?: SearchArea | null, waypoints?: Waypoint[], people?: typeof PEOPLE, packs?: InstalledPack[] }

// Draws the bar over a mission: its status (null: no mission is open), its search area, its
// waypoints and its people, with these packs installed.
function show({ status = 'planning', area = null, waypoints = [], people = [], packs = ARIZONA }: Shown = {}) {
    vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify(packs), { headers: { 'content-type': 'application/json' } })))
    render(
        <MissionContext value={{ mission: status && arizona(status), loadFailed: false, run: async () => '' }}>
            <SearchAreaContext value={{ area, loadedFor: 'az07', save: async () => '' }}>
                <WaypointsContext value={board(waypoints)}>
                    <PeopleContext value={{ roster: [], people, radios: [], groups: [], run: async () => '' }}>
                        <SetupBar />
                    </PeopleContext>
                </WaypointsContext>
            </SearchAreaContext>
        </MissionContext>,
    )
}

// Each step as a screen reader says it: "Search Area: done".
const steps = () => within(screen.getByRole('list', { name: 'Setup' })).getAllByRole('listitem').map((step) => step.getAttribute('aria-label'))

test('a mission in planning shows the four steps, none done', () => {
    show()
    expect(steps()).toEqual(['Search Area: not done', 'Offline Maps: not done', 'Mark CP: not done', 'Check In People: not done'])
})

test('placing the command post alone ticks Mark CP', () => {
    show({ waypoints: WAYPOINTS })
    expect(steps()).toEqual(['Search Area: not done', 'Offline Maps: not done', 'Mark CP: done', 'Check In People: not done'])
})

test('checking one person in alone ticks Check In People', () => {
    show({ people: PEOPLE })
    expect(steps()).toEqual(['Search Area: not done', 'Offline Maps: not done', 'Mark CP: not done', 'Check In People: done'])
})

test('with the area drawn, the command post placed and a person checked in, those three are ticked', async () => {
    show({ area: ARIZONA07_AREA, waypoints: WAYPOINTS, people: PEOPLE })
    await waitFor(() => expect(steps()).toEqual(
        ['Search Area: done', 'Offline Maps: maps missing', 'Mark CP: done', 'Check In People: done']))
})

test('Offline Maps is ticked when the installed packs cover the search area', async () => {
    show({ area: ARIZONA07_AREA, packs: [...ARIZONA, ARIZONA07_PACK] })
    await waitFor(() => expect(steps()[1]).toBe('Offline Maps: done'))
})

test('the steps are a checklist: none of them can be pressed', () => {
    show()
    expect(screen.queryByRole('button')).toBeNull()
})

// What a red Offline Maps step says under the bar

test('a red Offline Maps step says what is missing under the bar, with a greyed Download button', async () => {
    show({ area: ARIZONA07_AREA })  // the state pack only

    expect((await screen.findByRole('status')).textContent).toContain('No mission pack covers the search area.')
    const download = screen.getByRole('button', { name: 'Download' })
    expect(download.getAttribute('aria-disabled')).toBe('true')
    expect(download.title).toBe('Not available yet')
})

test('with the search area covered there is no line and no Download button', async () => {
    show({ area: ARIZONA07_AREA, packs: [...ARIZONA, ARIZONA07_PACK] })
    await waitFor(() => expect(steps()[1]).toBe('Offline Maps: done'))

    expect(screen.queryByRole('status')).toBeNull()
    expect(screen.queryByRole('button')).toBeNull()
})

test('with no search area yet there is no line: there is nothing to check', () => {
    show()
    expect(screen.queryByRole('status')).toBeNull()
})

test('the bar is gone once the mission has started', () => {
    show({ status: 'active' })
    expect(screen.queryByRole('list', { name: 'Setup' })).toBeNull()
})

test('with no mission open there is no bar', () => {
    show({ status: null })
    expect(screen.queryByRole('list', { name: 'Setup' })).toBeNull()
})
