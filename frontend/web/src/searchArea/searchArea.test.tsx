import type { Map as MapLibreMap } from 'maplibre-gl'
import { cleanup, render, waitFor } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import { MissionContext, type OpenMission } from '../mission/mission.ts'
import { useMapOverSearchArea, type SearchArea } from './searchArea.ts'

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
// open is the id of the open mission. It counts how often the area was asked for.
function pretendBackend(areas: Record<string, SearchArea | null>) {
    const backend = { open: '', asked: 0 }
    vi.stubGlobal('fetch', vi.fn(async (address: string) => {
        if (address !== '/api/mission/search-area') return new Response(null, { status: 204 })
        backend.asked += 1
        return new Response(JSON.stringify(areas[backend.open]), { headers: { 'content-type': 'application/json' } })
    }))
    return backend
}

// A pretend map that records where it was told to go.
function pretendMap() {
    return { fitBounds: vi.fn() }
}

// Draws nothing; it only runs the piece under test, with a mission on the board.
function Screen({ map, open, panelOpen = false }: { map: unknown, open: OpenMission | null, panelOpen?: boolean }) {
    return (
        <MissionContext value={{ mission: open, loadFailed: false, run: async () => '' }}>
            <Mover map={map as MapLibreMap} panelOpen={panelOpen} />
        </MissionContext>
    )
}
function Mover({ map, panelOpen }: { map: MapLibreMap, panelOpen: boolean }) {
    useMapOverSearchArea(map, panelOpen)
    return null
}

test('opening a mission moves the map over its search area', async () => {
    const backend = pretendBackend({ az07: ARIZONA07_AREA })
    const map = pretendMap()
    backend.open = 'az07'
    render(<Screen map={map} open={mission('az07')} />)

    await waitFor(() => expect(map.fitBounds).toHaveBeenCalledTimes(1))
    // West and south first, then east and north, as MapLibre takes them.
    expect(map.fitBounds.mock.calls[0][0]).toEqual([[-110.8083, 31.3926], [-110.544, 31.619]])
})

test('a mission with no search area leaves the map where it was', async () => {
    const backend = pretendBackend({ bc: null })
    const map = pretendMap()
    backend.open = 'bc'
    render(<Screen map={map} open={mission('bc')} />)

    await waitFor(() => expect(backend.asked).toBe(1))
    expect(map.fitBounds).not.toHaveBeenCalled()
})

test('with no mission open the search area is not asked for', async () => {
    const backend = pretendBackend({})
    const map = pretendMap()
    render(<Screen map={map} open={null} />)

    await Promise.resolve()
    expect(backend.asked).toBe(0)
    expect(map.fitBounds).not.toHaveBeenCalled()
})

test('the map moves again when another mission is opened, and not when the same one changes', async () => {
    const backend = pretendBackend({ az07: ARIZONA07_AREA, other: { min_lat: 40, min_lon: -106, max_lat: 40.1, max_lon: -105.9 } })
    const map = pretendMap()
    backend.open = 'az07'
    const screen = render(<Screen map={map} open={mission('az07')} />)
    await waitFor(() => expect(map.fitBounds).toHaveBeenCalledTimes(1))

    // The same mission with a change, such as a started session: the map stays.
    screen.rerender(<Screen map={map} open={{ ...mission('az07'), status: 'active' }} />)
    await Promise.resolve()
    expect(backend.asked).toBe(1)

    backend.open = 'other'
    screen.rerender(<Screen map={map} open={mission('other')} />)
    await waitFor(() => expect(map.fitBounds).toHaveBeenCalledTimes(2))
    expect(map.fitBounds.mock.calls[1][0]).toEqual([[-106, 40], [-105.9, 40.1]])
})

test('with a panel open the area is fitted beside the panel, not under it', async () => {
    const backend = pretendBackend({ az07: ARIZONA07_AREA })
    const map = pretendMap()
    backend.open = 'az07'
    render(<Screen map={map} open={mission('az07')} panelOpen />)

    await waitFor(() => expect(map.fitBounds).toHaveBeenCalledTimes(1))
    const { padding } = map.fitBounds.mock.calls[0][1]
    expect(padding.left).toBeGreaterThan(padding.right)
})
