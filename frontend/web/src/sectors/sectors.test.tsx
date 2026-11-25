import { act, cleanup, render, screen, waitFor } from '@testing-library/react'
import { useEffect } from 'react'
import { afterEach, expect, test, vi } from 'vitest'
import { MissionContext, type MissionStatus, type OpenMission } from '../mission/mission.ts'
import { NEVER_HELD } from './sample.ts'
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
        created_time: '2025-04-14T03:35:00Z', completed_time: null, ...NEVER_HELD,
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
        const one = address.match(/^\/api\/mission\/sectors\/(\d+)(\/corners)?$/)  // a route for one sector
        if (one) {
            if (backend.refuses) return json({ detail: backend.refuses }, 409)
            const id = Number(one[1])
            if (request?.method === 'DELETE') {
                sectors[backend.open] = sectors[backend.open].filter((s) => s.id !== id)
                return new Response(null, { status: 204 })
            }
            backend.sent = JSON.parse(request!.body as string)
            const changed = { ...sectors[backend.open].find((s) => s.id === id)!, corners: (backend.sent as { corners: Sector['corners'] }).corners }
            sectors[backend.open] = sectors[backend.open].map((s) => s.id === id ? changed : s)
            return json(changed)
        }
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
    return (
        <>
            <p data-testid="names">{read.sectors.map((s) => s.name).join(' ')}</p>
            <p data-testid="corners">{read.sectors.map((s) => s.corners.length).join(' ')}</p>
        </>
    )
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
    // board is set by an effect, which can run just after the names reach the page.
    await waitFor(() => expect(board.loadedFor).toBe('az07'))
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

// Opens Bear Creek with S1 and S2 on the board, three corners each.
async function bearCreekWithTwo() {
    const backend = pretendBackend({ bc: [sector(1), sector(2)] })
    backend.open = 'bc'
    render(<Screen open={mission('bc')} />)
    await waitFor(() => expect(names()).toBe('S1 S2'))
    return backend
}

test("a sector's new shape is sent, and the board shows it once saved", async () => {
    const backend = await bearCreekWithTwo()
    const four = [{ lat: 40.0, lon: -105.6 }, { lat: 40.05, lon: -105.6 }, { lat: 40.05, lon: -105.55 }, { lat: 40.0, lon: -105.55 }]

    let reason: string | undefined
    await act(async () => { reason = await board.changeShape(2, four) })

    expect(reason).toBe('')
    expect(backend.sent).toEqual({ corners: four })
    expect(screen.getByTestId('corners').textContent).toBe('3 4')
})

test('a deleted sector leaves the board once the backend has deleted it', async () => {
    await bearCreekWithTwo()

    let reason: string | undefined
    await act(async () => { reason = await board.remove(1) })

    expect(reason).toBe('')
    expect(names()).toBe('S2')
})

test("a refused change or delete leaves the board as it was, and the backend's reason is given", async () => {
    const backend = await bearCreekWithTwo()
    backend.refuses = 'S1 has been assigned, so it cannot be deleted.'

    let reason: string | undefined
    await act(async () => { reason = await board.remove(1) })

    expect(reason).toBe('S1 has been assigned, so it cannot be deleted.')
    expect(names()).toBe('S1 S2')
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

// The rest of a sector's life. A backend that holds S1 and S2, drawn, and Group 1 holding
// S1; giving S2 to Group 1 releases S1, so one request changes two sectors.
function backendWithGroups() {
    let sectors = [{ ...sector(1), group_id: 1 as number | null }, sector(2)]
    const sent: { address: string, body: unknown }[] = []
    const refuses = { reason: '' }
    const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { 'content-type': 'application/json' } })
    vi.stubGlobal('fetch', vi.fn(async (address: string, request?: RequestInit) => {
        if (address === '/api/mission/sectors') return json(sectors)
        sent.push({ address, body: request?.body ? JSON.parse(request.body as string) : null })
        if (refuses.reason) return json({ detail: refuses.reason }, 409)
        if (address === '/api/mission/sectors/2/assign') {
            sectors = [{ ...sectors[0], group_id: null }, { ...sectors[1], group_id: 1 }]
        }
        return json(sectors[1])
    }))
    return { sent, refuses }
}
function Holders() {
    const read = useSectors()
    useEffect(() => { board = read })
    return <p data-testid="holders">{read.sectors.map((s) => `${s.name}:${s.group_id}`).join(' ')}</p>
}
async function openWithGroups() {
    const backend = backendWithGroups()
    render(
        <MissionContext value={{ mission: mission('bc', 'active'), loadFailed: false, run: async () => '' }}>
            <SectorsProvider><Holders /></SectorsProvider>
        </MissionContext>,
    )
    await waitFor(() => expect(screen.getByTestId('holders').textContent).toBe('S1:1 S2:null'))
    return backend
}

test('assigning a sector reads every sector again, since the group may have let go of another', async () => {
    const backend = await openWithGroups()

    let reason: string | undefined
    await act(async () => { reason = await board.assign(2, 1) })

    expect(reason).toBe('')
    expect(backend.sent).toEqual([{ address: '/api/mission/sectors/2/assign', body: { group_id: 1 } }])
    expect(screen.getByTestId('holders').textContent).toBe('S1:null S2:1')
})

test('release, mark entered and mark completed each go to their own route', async () => {
    const backend = await openWithGroups()

    await act(async () => {
        await board.release(1)
        await board.markEntered(1, 7)
        await board.complete(1)
    })

    expect(backend.sent).toEqual([
        { address: '/api/mission/sectors/1/release', body: null },
        { address: '/api/mission/sectors/1/entered', body: { radio_id: 7 } },
        { address: '/api/mission/sectors/1/complete', body: null },
    ])
})

test("a refused assignment leaves the board as it was, and the backend's reason is given", async () => {
    const backend = await openWithGroups()
    backend.refuses.reason = 'Group 3 has no teams, so it cannot be given a sector.'

    let reason: string | undefined
    await act(async () => { reason = await board.assign(2, 3) })

    expect(reason).toBe('Group 3 has no teams, so it cannot be given a sector.')
    expect(screen.getByTestId('holders').textContent).toBe('S1:1 S2:null')
})
