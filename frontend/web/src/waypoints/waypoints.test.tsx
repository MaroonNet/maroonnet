import { act, cleanup, render, screen, waitFor } from '@testing-library/react'
import { useEffect } from 'react'
import { afterEach, expect, test, vi } from 'vitest'
import { MissionContext, type OpenMission } from '../mission/mission.ts'
import { arizona } from '../teams/sample.ts'
import { ARIZONA07, waypoint } from './sample.ts'
import { useWaypoints, type Placing, type WaypointsBoard } from './waypoints.ts'
import WaypointsProvider from './WaypointsProvider.tsx'

afterEach(() => {
    cleanup()
    vi.unstubAllGlobals()
})

const HAZARD: Placing = { kind: 'hazard', lat: 31.5, lon: -110.67, name: 'Mine shaft', description: '', note: '' }

// A pretend backend. It keeps the requests it was sent, and answers each from the list.
function backend(...answers: { status?: number, body: unknown }[]) {
    const requests: { address: string, method: string, body: unknown }[] = []
    vi.stubGlobal('fetch', async (address: string, options: { method?: string, body?: string } = {}) => {
        requests.push({ address, method: options.method ?? 'GET', body: options.body ? JSON.parse(options.body) : undefined })
        const { status = 200, body } = answers.shift() ?? { body: [] }
        return { ok: status < 300, status, statusText: '', json: async () => body }
    })
    return requests
}

// Draws the board's waypoint names, and hands the board to the test.
let held: WaypointsBoard  // the board as it last was, for a test to call
function Names() {
    const read = useWaypoints()
    useEffect(() => { held = read })
    return <p data-testid="names">{read.waypoints.map((w) => w.name).join(', ')}</p>
}

function show(mission: OpenMission | null) {
    return render(
        <MissionContext value={{ mission, loadFailed: false, run: async () => '' }}>
            <WaypointsProvider><Names /></WaypointsProvider>
        </MissionContext>,
    )
}

const names = () => screen.getByTestId('names').textContent

test('the board reads the open mission\'s waypoints', async () => {
    const requests = backend({ body: ARIZONA07 })
    show(arizona())
    await waitFor(() => expect(names()).toBe('Command post, Start point, LZ 1, Boot prints, Helicopter sighting, Subject found'))
    expect(requests).toEqual([{ address: '/api/mission/waypoints', method: 'GET', body: undefined }])
})

test('with no mission open the board holds none and asks nothing', () => {
    const requests = backend()
    show(null)
    expect(names()).toBe('')
    expect(requests).toEqual([])
})

test('adding a waypoint saves it, reads every waypoint again, and answers with it as saved', async () => {
    const saved = waypoint(7, 'hazard', 'Mine shaft')
    const requests = backend({ body: [] }, { status: 201, body: saved }, { body: [saved] })
    show(arizona())
    await waitFor(() => expect(requests).toHaveLength(1))

    let answer: unknown
    await act(async () => { answer = await held.add(HAZARD) })

    expect(answer).toEqual(saved)
    expect(requests[1]).toEqual({ address: '/api/mission/waypoints', method: 'POST', body: HAZARD })
    expect(names()).toBe('Mine shaft')
})

test('changing a waypoint answers with the new one that took its place', async () => {
    const changed = waypoint(8, 'hazard', 'Old mine shaft')
    const requests = backend({ body: [waypoint(7, 'hazard', 'Mine shaft')] }, { body: changed }, { body: [changed] })
    show(arizona())
    await waitFor(() => expect(names()).toBe('Mine shaft'))

    let answer: unknown
    await act(async () => { answer = await held.change(7, { ...HAZARD, name: 'Old mine shaft' }) })

    expect(answer).toEqual(changed)
    expect(requests[1].address).toBe('/api/mission/waypoints/7')
    expect(requests[1].method).toBe('PUT')
    expect(names()).toBe('Old mine shaft')
})

test('removing a waypoint takes it off the board', async () => {
    const requests = backend({ body: [waypoint(7, 'hazard', 'Mine shaft')] }, { status: 204, body: null }, { body: [] })
    show(arizona())
    await waitFor(() => expect(names()).toBe('Mine shaft'))

    let answer: unknown
    await act(async () => { answer = await held.remove(7) })

    expect(answer).toBe('')
    expect(requests[1]).toEqual({ address: '/api/mission/waypoints/7', method: 'DELETE', body: undefined })
    expect(names()).toBe('')
})

test('a refused change answers with the backend\'s reason and leaves the board as it was', async () => {
    backend({ body: [waypoint(7, 'hazard', 'Mine shaft')] }, { status: 409, body: { detail: 'This session is paused, so nothing in it can be changed.' } })
    show(arizona())
    await waitFor(() => expect(names()).toBe('Mine shaft'))

    let answer: unknown
    await act(async () => { answer = await held.remove(7) })

    expect(answer).toBe('This session is paused, so nothing in it can be changed.')
    expect(names()).toBe('Mine shaft')
})

test('the waypoints are read again when the next session starts', async () => {
    const requests = backend({ body: ARIZONA07 }, { body: ARIZONA07.slice(0, 2) })
    const { rerender } = show(arizona('paused'))
    await waitFor(() => expect(requests).toHaveLength(1))

    rerender(
        <MissionContext value={{ mission: { ...arizona(), session: 2 }, loadFailed: false, run: async () => '' }}>
            <WaypointsProvider><Names /></WaypointsProvider>
        </MissionContext>,
    )

    await waitFor(() => expect(names()).toBe('Command post, Start point'))
})
