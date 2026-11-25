import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import { PeopleContext } from '../people/people.ts'
import { SearchAreaContext, type SearchArea } from '../searchArea/searchArea.ts'
import type { InstalledPack } from '../setup/packs.ts'
import { ARIZONA, ARIZONA07_AREA, ARIZONA07_PACK } from '../setup/sample.ts'
import { arizona, PEOPLE } from '../teams/sample.ts'
import { ARIZONA07 as WAYPOINTS, board } from '../waypoints/sample.ts'
import { WaypointsContext, type Waypoint } from '../waypoints/waypoints.ts'
import { MissionContext } from './mission.ts'
import OpenMissionView from './OpenMissionView.tsx'

afterEach(() => {
    cleanup()
    vi.unstubAllGlobals()
})

type Shown = { area?: SearchArea | null, waypoints?: Waypoint[], people?: typeof PEOPLE, packs?: InstalledPack[] }

// Draws the Mission panel's view of a mission in planning, with these packs installed. The
// list it returns fills with each request that changes the mission.
function show({ area = null, waypoints = [], people = [], packs = [...ARIZONA, ARIZONA07_PACK] }: Shown = {}) {
    const sent: string[] = []
    vi.stubGlobal('fetch', vi.fn(async (address: string, request?: RequestInit) => {
        if (request?.method === 'POST') sent.push(address)
        const answer = address === '/api/maps/packs' ? packs : arizona('active')
        return new Response(JSON.stringify(answer), { headers: { 'content-type': 'application/json' } })
    }))
    const mission = arizona('planning')
    render(
        <MissionContext value={{ mission, loadFailed: false, run: async (request) => { await request; return '' } }}>
            <SearchAreaContext value={{ area, loadedFor: 'az07', save: async () => '' }}>
                <WaypointsContext value={board(waypoints)}>
                    <PeopleContext value={{ roster: [], people, radios: [], groups: [], run: async () => '' }}>
                        <OpenMissionView mission={mission} />
                    </PeopleContext>
                </WaypointsContext>
            </SearchAreaContext>
        </MissionContext>,
    )
    return sent
}

// Lets the answer with the installed packs arrive, and the view take it in. Nothing on
// screen shows it, so the test waits one turn of the clock in place of looking for a change.
const packsRead = () => act(async () => { await new Promise((done) => setTimeout(done, 0)) })

const press = (name: string) => fireEvent.click(screen.getByRole('button', { name }))
const lines = () => within(screen.getByRole('dialog')).getAllByRole('listitem').map((line) => line.textContent)

test('Start Mission with nothing set up asks first, and lists what is not done', () => {
    const sent = show()

    press('Start Mission')

    expect(screen.getByRole('dialog', { name: 'Start the mission?' })).toBeTruthy()
    expect(lines()).toEqual(['No search area.', 'Command post not placed.', 'Nobody is checked in.'])
    expect(sent).toEqual([])  // nothing is started until the answer
})

test('Start Anyway starts the mission', async () => {
    const sent = show()

    press('Start Mission')
    press('Start Anyway')

    await waitFor(() => expect(sent).toEqual(['/api/mission/start']))
    expect(screen.queryByRole('dialog')).toBeNull()
})

test('Cancel closes the box and starts nothing', () => {
    const sent = show()

    press('Start Mission')
    press('Cancel')

    expect(screen.queryByRole('dialog')).toBeNull()
    expect(sent).toEqual([])
})

test('a red maps step is listed, and does not block the start', async () => {
    const sent = show({ area: ARIZONA07_AREA, waypoints: WAYPOINTS, people: PEOPLE, packs: ARIZONA })
    await packsRead()

    press('Start Mission')
    expect(lines()).toEqual(['No mission pack covers the search area.'])
    press('Start Anyway')

    await waitFor(() => expect(sent).toEqual(['/api/mission/start']))
})

test('with all four steps done, Start Mission starts at once with no box', async () => {
    const sent = show({ area: ARIZONA07_AREA, waypoints: WAYPOINTS, people: PEOPLE })
    await packsRead()

    press('Start Mission')

    expect(screen.queryByRole('dialog')).toBeNull()
    await waitFor(() => expect(sent).toEqual(['/api/mission/start']))
})
