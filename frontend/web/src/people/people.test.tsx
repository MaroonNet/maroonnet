import { act, cleanup, render, screen, waitFor } from '@testing-library/react'
import { useEffect } from 'react'
import { afterEach, expect, test, vi } from 'vitest'
import { MissionContext, type MissionStatus, type OpenMission } from '../mission/mission.ts'
import { checkIn, usePeople, type PeopleBoard } from './people.ts'
import PeopleProvider from './PeopleProvider.tsx'

afterEach(() => {
    cleanup()
    vi.unstubAllGlobals()
})

function mission(id: string, status: MissionStatus = 'planning'): OpenMission {
    return {
        id, name: id, time_zone: 'America/Phoenix', status, session: 1, start_time: null,
        end_time: null, sessions: [], asks_to_continue: false,
    }
}

// Stands in for the backend: a roster of one, and a mission of one person who is checked
// in once the check-in route is asked. It counts how often each list was read.
function pretendBackend() {
    const backend = { rosterReads: 0, peopleReads: 0, checkedIn: false, refuses: '' }
    const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { 'content-type': 'application/json' } })
    vi.stubGlobal('fetch', vi.fn(async (address: string, request?: RequestInit) => {
        if (address === '/api/roster') {
            backend.rosterReads += 1
            return json([{ id: 1, first_name: 'Ana', middle_initial: null, last_name: 'Ruiz', phone: null }])
        }
        if (address === '/api/mission/people') {
            backend.peopleReads += 1
            return json([{ id: 1, first_name: 'Ana', last_name: 'Ruiz', checked_in: backend.checkedIn }])
        }
        if (address === '/api/mission/people/1/check-in' && request?.method === 'POST') {
            if (backend.refuses) return json({ detail: backend.refuses }, 409)
            backend.checkedIn = true
            return json({})
        }
        return new Response(null, { status: 204 })
    }))
    return backend
}

// Shows what the board holds, and hands the board to the test.
let board: PeopleBoard
function Reader() {
    const now = usePeople()
    useEffect(() => { board = now })
    return <p>{now.roster.length} on roster, {now.people.filter((person) => person.checked_in).length} of {now.people.length} checked in</p>
}

function Screen({ open }: { open: OpenMission | null }) {
    return (
        <MissionContext value={{ mission: open, loadFailed: false, run: async () => '' }}>
            <PeopleProvider><Reader /></PeopleProvider>
        </MissionContext>
    )
}

test('the roster is read with no mission open, and the people once one is', async () => {
    const backend = pretendBackend()
    const { rerender } = render(<Screen open={null} />)
    await screen.findByText('1 on roster, 0 of 0 checked in')
    expect(backend.peopleReads).toBe(0)

    rerender(<Screen open={mission('bc')} />)
    await screen.findByText('1 on roster, 0 of 1 checked in')
})

test('the people are read again when the session ends, and dropped when the mission closes', async () => {
    const backend = pretendBackend()
    const { rerender } = render(<Screen open={mission('bc', 'active')} />)
    await screen.findByText('1 on roster, 0 of 1 checked in')

    rerender(<Screen open={mission('bc', 'paused')} />)
    await waitFor(() => expect(backend.peopleReads).toBe(2))

    rerender(<Screen open={null} />)
    await screen.findByText('1 on roster, 0 of 0 checked in')
})

test('a change that worked is followed by reading both lists again', async () => {
    const backend = pretendBackend()
    render(<Screen open={mission('bc')} />)
    await screen.findByText('1 on roster, 0 of 1 checked in')

    let reason = 'not answered'
    await act(async () => { reason = await board.run(checkIn(1)) })

    expect(reason).toBe('')
    await screen.findByText('1 on roster, 1 of 1 checked in')
    expect(backend.rosterReads).toBe(2)
})

test('a change the backend refuses answers with its reason, and the board stays as it was', async () => {
    const backend = pretendBackend()
    backend.refuses = 'Ana Ruiz is already checked in.'
    render(<Screen open={mission('bc')} />)
    await screen.findByText('1 on roster, 0 of 1 checked in')

    let reason = ''
    await act(async () => { reason = await board.run(checkIn(1)) })

    expect(reason).toBe('Ana Ruiz is already checked in.')
    expect(screen.getByText('1 on roster, 0 of 1 checked in')).toBeTruthy()
})
