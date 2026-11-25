import { cleanup, render, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import { MissionContext, type OpenMission } from '../mission/mission.ts'
import { arizona, TRACKS } from './sample.ts'
import { useTracks } from './tracks.ts'
import TracksProvider from './TracksProvider.tsx'

afterEach(() => {
    cleanup()
    vi.unstubAllGlobals()
})

// A pretend backend. It keeps the addresses it was asked, and answers each from the list.
function backend(...answers: unknown[]) {
    const asked: string[] = []
    vi.stubGlobal('fetch', async (address: string) => {
        asked.push(address)
        return { ok: true, status: 200, statusText: '', json: async () => answers.shift() ?? [] }
    })
    return asked
}

// Draws which radios the board has a track for.
function Radios() {
    return <p data-testid="radios">{useTracks().map((track) => track.radio_id).join(', ')}</p>
}

function show(mission: OpenMission | null) {
    const board = (open: OpenMission | null) => (
        <MissionContext value={{ mission: open, loadFailed: false, run: async () => '' }}>
            <TracksProvider><Radios /></TracksProvider>
        </MissionContext>
    )
    const { rerender } = render(board(mission))
    return (next: OpenMission | null) => rerender(board(next))
}

const radios = () => screen.getByTestId('radios').textContent

test("the board reads the open mission's tracks, once", async () => {
    const asked = backend(TRACKS)
    show(arizona())
    await waitFor(() => expect(radios()).toBe('1, 4'))
    expect(asked).toEqual(['/api/mission/tracks'])
})

test('with no mission open the board holds none and asks nothing', () => {
    const asked = backend()
    show(null)
    expect(radios()).toBe('')
    expect(asked).toEqual([])
})

test("a new session has its own file, so its tracks are read, and the last session's are not shown", async () => {
    const asked = backend(TRACKS, [])
    const change = show(arizona())
    await waitFor(() => expect(radios()).toBe('1, 4'))

    change({ ...arizona(), session: 2 })

    await waitFor(() => expect(asked).toHaveLength(2))
    await waitFor(() => expect(radios()).toBe(''))
})

test('when the mission is closed the board holds none', async () => {
    backend(TRACKS)
    const change = show(arizona())
    await waitFor(() => expect(radios()).toBe('1, 4'))

    change(null)

    expect(radios()).toBe('')
})
