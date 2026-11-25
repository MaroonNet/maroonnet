import { act, cleanup, render, screen, waitFor } from '@testing-library/react'
import { useEffect } from 'react'
import { afterEach, expect, test, vi } from 'vitest'
import { MissionContext, type OpenMission } from '../mission/mission.ts'
import { useMapOverSearchArea, useSearchArea, type SearchArea, type SearchAreaBoard } from './searchArea.ts'
import SearchAreaProvider from './SearchAreaProvider.tsx'

afterEach(() => {
    cleanup()
    vi.unstubAllGlobals()
})

// Arizona07's search area, as the backend answers it.
const ARIZONA07_AREA: SearchArea = { min_lat: 31.3926, min_lon: -110.8083, max_lat: 31.619, max_lon: -110.544 }

function mission(id: string): OpenMission {
    return {
        id, name: id, time_zone: 'America/Phoenix', status: 'planning', session: 1, start_time: null,
        end_time: null, sessions: [], asks_to_continue: false,
    }
}

// Stands in for the backend: areas holds each mission's search area, by mission id, and
// open is the id of the open mission. It counts how often the area was asked for. A new
// area sent to it is saved, unless refuses holds a reason.
function pretendBackend(areas: Record<string, SearchArea | null>) {
    const backend = { open: '', asked: 0, refuses: '' }
    const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { 'content-type': 'application/json' } })
    vi.stubGlobal('fetch', vi.fn(async (address: string, request?: RequestInit) => {
        if (address !== '/api/mission/search-area') return new Response(null, { status: 204 })
        if (request?.method === 'PUT') {
            if (backend.refuses) return json({ detail: backend.refuses }, 409)
            areas[backend.open] = JSON.parse(request.body as string)
            return json(areas[backend.open])
        }
        backend.asked += 1
        return json(areas[backend.open])
    }))
    return backend
}

// The shared board the map is read from. Each test puts its own pretend map on it.
const board = vi.hoisted(() => ({ map: null as unknown }))
vi.mock('../map/missionMap.ts', () => ({ useMissionMap: () => board.map }))

// A pretend map that records where it was told to go.
function pretendMap() {
    const map = { fitBounds: vi.fn() }
    board.map = map
    return map
}

// The pieces under test, with a mission on its board: the search area board, the piece
// that moves the map, and a line of text showing the area on the board.
function Screen({ open, panelOpen = false }: { open: OpenMission | null, panelOpen?: boolean }) {
    return (
        <MissionContext value={{ mission: open, loadFailed: false, run: async () => '' }}>
            <SearchAreaProvider>
                <Mover panelOpen={panelOpen} />
            </SearchAreaProvider>
        </MissionContext>
    )
}
let saveArea: SearchAreaBoard['save']  // the board's save, for a test to call
function Mover({ panelOpen }: { panelOpen: boolean }) {
    useMapOverSearchArea(panelOpen)
    const { area, save } = useSearchArea()
    useEffect(() => { saveArea = save })
    return <p data-testid="area">{JSON.stringify(area)}</p>
}
const areaOnBoard = () => JSON.parse(screen.getByTestId('area').textContent!)

test('opening a mission moves the map over its search area', async () => {
    const backend = pretendBackend({ az07: ARIZONA07_AREA })
    const map = pretendMap()
    backend.open = 'az07'
    render(<Screen open={mission('az07')} />)

    await waitFor(() => expect(map.fitBounds).toHaveBeenCalledTimes(1))
    // West and south first, then east and north, as MapLibre takes them.
    expect(map.fitBounds.mock.calls[0][0]).toEqual([[-110.8083, 31.3926], [-110.544, 31.619]])
})

test('a mission with no search area leaves the map where it was', async () => {
    const backend = pretendBackend({ bc: null })
    const map = pretendMap()
    backend.open = 'bc'
    render(<Screen open={mission('bc')} />)

    await waitFor(() => expect(backend.asked).toBe(1))
    expect(map.fitBounds).not.toHaveBeenCalled()
})

test('with no mission open the search area is not asked for', async () => {
    const backend = pretendBackend({})
    const map = pretendMap()
    render(<Screen open={null} />)

    await Promise.resolve()
    expect(backend.asked).toBe(0)
    expect(map.fitBounds).not.toHaveBeenCalled()
})

test('the map moves again when another mission is opened, and not when the same one changes', async () => {
    const backend = pretendBackend({ az07: ARIZONA07_AREA, other: { min_lat: 40, min_lon: -106, max_lat: 40.1, max_lon: -105.9 } })
    const map = pretendMap()
    backend.open = 'az07'
    const page = render(<Screen open={mission('az07')} />)
    await waitFor(() => expect(map.fitBounds).toHaveBeenCalledTimes(1))

    // The same mission with a change, such as a started session: the map stays.
    page.rerender(<Screen open={{ ...mission('az07'), status: 'active' }} />)
    await Promise.resolve()
    expect(backend.asked).toBe(1)

    backend.open = 'other'
    page.rerender(<Screen open={mission('other')} />)
    await waitFor(() => expect(map.fitBounds).toHaveBeenCalledTimes(2))
    expect(map.fitBounds.mock.calls[1][0]).toEqual([[-106, 40], [-105.9, 40.1]])
})

test('with a panel open the area is fitted beside the panel, not under it', async () => {
    const backend = pretendBackend({ az07: ARIZONA07_AREA })
    const map = pretendMap()
    backend.open = 'az07'
    render(<Screen open={mission('az07')} panelOpen />)

    await waitFor(() => expect(map.fitBounds).toHaveBeenCalledTimes(1))
    const { padding } = map.fitBounds.mock.calls[0][1]
    expect(padding.left).toBeGreaterThan(padding.right)
})

const BEAR_CREEK_AREA: SearchArea = { min_lat: 39.9, min_lon: -105.7, max_lat: 40.1, max_lon: -105.5 }

test('a saved search area goes on the board, and the map stays where it is', async () => {
    const backend = pretendBackend({ bc: null })
    const map = pretendMap()
    backend.open = 'bc'
    render(<Screen open={mission('bc')} />)
    await waitFor(() => expect(backend.asked).toBe(1))
    expect(areaOnBoard()).toBeNull()

    let reason = 'not answered'
    await act(async () => { reason = await saveArea(BEAR_CREEK_AREA) })

    expect(reason).toBe('')  // empty: it was saved
    expect(areaOnBoard()).toEqual(BEAR_CREEK_AREA)
    expect(map.fitBounds).not.toHaveBeenCalled()
})

test('a search area the backend refuses leaves the board as it was, and gives the reason', async () => {
    const backend = pretendBackend({ az07: ARIZONA07_AREA })
    pretendMap()
    backend.open = 'az07'
    backend.refuses = 'This session is paused, so nothing in it can be changed.'
    render(<Screen open={mission('az07')} />)
    await waitFor(() => expect(areaOnBoard()).toEqual(ARIZONA07_AREA))

    let reason = ''
    await act(async () => { reason = await saveArea(BEAR_CREEK_AREA) })

    expect(reason).toBe('This session is paused, so nothing in it can be changed.')
    expect(areaOnBoard()).toEqual(ARIZONA07_AREA)
})

test('closing the mission takes its search area off the board', async () => {
    const backend = pretendBackend({ az07: ARIZONA07_AREA })
    pretendMap()
    backend.open = 'az07'
    const page = render(<Screen open={mission('az07')} />)
    await waitFor(() => expect(areaOnBoard()).toEqual(ARIZONA07_AREA))

    page.rerender(<Screen open={null} />)

    expect(areaOnBoard()).toBeNull()
})
