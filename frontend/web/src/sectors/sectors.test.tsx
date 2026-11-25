import { act, cleanup, render, screen, waitFor } from '@testing-library/react'
import { useEffect } from 'react'
import { afterEach, expect, test, vi } from 'vitest'
import { MissionContext, type MissionStatus, type OpenMission } from '../mission/mission.ts'
import { useSectors, type Sector, type SectorsBoard } from './sectors.ts'
import SectorsProvider from './SectorsProvider.tsx'

afterEach(() => {
    cleanup()
    vi.unstubAllGlobals()
})

// A sector as the backend answers it.
function sector(id: number, status: Sector['status'] = 'drawn'): Sector {
    return {
        id, name: `S${id}`, status, group_id: null, can_edit: status === 'drawn',
        corners: [{ lat: 31.5, lon: -110.7 }, { lat: 31.51, lon: -110.7 }, { lat: 31.51, lon: -110.69 }],
        created_time: '2025-04-14T03:35:00Z', completed_time: null,
    }
}

function mission(id: string, status: MissionStatus = 'planning'): OpenMission {
    return {
        id, name: id, time_zone: 'America/Phoenix', status, session: 1, start_time: null,
        end_time: null, sessions: [], asks_to_continue: false,
    }
}

// Stands in for the backend. sectors holds each mission's sectors, by mission id, and open
// is the open mission's id. It counts how often the list was asked for. A new sector sent
// to it is saved with the next number, unless refuses holds a reason.
function pretendBackend(sectors: Record<string, Sector[]>) {
    const backend = { open: '', asked: 0, refuses: '', sent: null as unknown }
    const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { 'content-type': 'application/json' } })
    vi.stubGlobal('fetch', vi.fn(async (address: string, request?: RequestInit) => {
        if (address !== '/api/mission/sectors') return new Response(null, { status: 204 })
        if (request?.method === 'POST') {
            if (backend.refuses) return json({ detail: backend.refuses }, 409)
            backend.sent = JSON.parse(request.body as string)
            const added = sector(sectors[backend.open].length + 1)
            sectors[backend.open] = [...sectors[backend.open], added]
            return json(added, 201)
        }
        backend.asked += 1
        return json(sectors[backend.open])
    }))
    return backend
}

let board: SectorsBoard  // the board as it last was, for a test to read and call
function Reader() {
    const read = useSectors()
    useEffect(() => { board = read })
    return <p data-testid="names">{read.sectors.map((s) => s.name).join(' ')}</p>
}
function Screen({ open }: { open: OpenMission | null }) {
    return (
        <MissionContext value={{ mission: open, loadFailed: false, run: async () => '' }}>
            <SectorsProvider>
                <Reader />
            </SectorsProvider>
        </MissionContext>
    )
}
const names = () => screen.getByTestId('names').textContent

test("opening a mission puts its sectors on the board", async () => {
    const backend = pretendBackend({ az07: [sector(1, 'completed'), sector(4, 'partial'), sector(7)] })
    backend.open = 'az07'
    render(<Screen open={mission('az07')} />)

    await waitFor(() => expect(names()).toBe('S1 S4 S7'))
    expect(board.loadedFor).toBe('az07')
})

test('with no mission open the board holds no sectors and asks for none', () => {
    const backend = pretendBackend({})
    render(<Screen open={null} />)

    expect(names()).toBe('')
    expect(backend.asked).toBe(0)
})

test("another mission's sectors replace the first one's", async () => {
    const backend = pretendBackend({ az07: [sector(1)], bc: [] })
    backend.open = 'az07'
    const { rerender } = render(<Screen open={mission('az07')} />)
    await waitFor(() => expect(names()).toBe('S1'))

    backend.open = 'bc'
    rerender(<Screen open={mission('bc')} />)

    await waitFor(() => expect(board.loadedFor).toBe('bc'))
    expect(names()).toBe('')
})

test('ending or reopening the mission reads the sectors again, since that can change their status', async () => {
    const backend = pretendBackend({ az07: [sector(1)] })
    backend.open = 'az07'
    const { rerender } = render(<Screen open={mission('az07', 'active')} />)
    await waitFor(() => expect(backend.asked).toBe(1))

    rerender(<Screen open={mission('az07', 'ended')} />)

    await waitFor(() => expect(backend.asked).toBe(2))
})

test('a new sector is sent with its corners, and the board shows it once saved', async () => {
    const backend = pretendBackend({ bc: [] })
    backend.open = 'bc'
    render(<Screen open={mission('bc')} />)
    await waitFor(() => expect(board.loadedFor).toBe('bc'))
    const corners = [{ lat: 40.0, lon: -105.6 }, { lat: 40.05, lon: -105.6 }, { lat: 40.05, lon: -105.55 }]

    let reason: string | undefined
    await act(async () => { reason = await board.add(corners) })

    expect(reason).toBe('')
    expect(backend.sent).toEqual({ corners })
    expect(names()).toBe('S1')
})

test("a refused sector is not put on the board, and the backend's reason is given", async () => {
    const backend = pretendBackend({ bc: [] })
    backend.open = 'bc'
    render(<Screen open={mission('bc')} />)
    await waitFor(() => expect(board.loadedFor).toBe('bc'))
    backend.refuses = 'A sector must be inside the search area.'

    let reason: string | undefined
    await act(async () => { reason = await board.add([{ lat: 41, lon: -105.6 }, { lat: 41.1, lon: -105.6 }, { lat: 41.1, lon: -105.5 }]) })

    expect(reason).toBe('A sector must be inside the search area.')
    expect(names()).toBe('')
})
