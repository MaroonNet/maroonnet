import { act, cleanup, render, screen, waitFor } from '@testing-library/react'
import { useEffect } from 'react'
import { afterEach, expect, test, vi } from 'vitest'
import { MissionContext, type OpenMission } from '../mission/mission.ts'
import { arizona } from '../teams/sample.ts'
import { useProbability, type MapRequest, type ProbabilityBoard } from './probability.ts'
import ProbabilityProvider from './ProbabilityProvider.tsx'
import { overlay } from './sample.ts'

afterEach(() => {
    cleanup()
    vi.unstubAllGlobals()
})

const START_POINT: MapRequest = { lon: -110.6762167, lat: 31.5057167, model: 'model_a', category: 'hiker', elapsed_h: 6 }

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

// Draws the id of the board's map, and hands the board to the test.
let held: ProbabilityBoard  // the board as it last was, for a test to call
function Newest() {
    const read = useProbability()
    useEffect(() => { held = read })
    return <p data-testid="newest">{read.newest?.id ?? 'none'}</p>
}

function show(mission: OpenMission | null) {
    return render(
        <MissionContext value={{ mission, loadFailed: false, run: async () => '' }}>
            <ProbabilityProvider><Newest /></ProbabilityProvider>
        </MissionContext>,
    )
}

const newest = () => screen.getByTestId('newest').textContent

test('the board holds the newest map kept with the open mission', async () => {
    // The backend lists a mission's maps newest first.
    const requests = backend({ body: [overlay('140000'), overlay('120000')] })
    show(arizona())
    await waitFor(() => expect(newest()).toBe('20261125-140000_hiker'))
    expect(requests).toEqual([{ address: '/api/spm/predictions', method: 'GET', body: undefined }])
})

test('a mission with no map made holds none', async () => {
    const requests = backend({ body: [] })
    show(arizona())
    await waitFor(() => expect(requests).toHaveLength(1))
    expect(newest()).toBe('none')
})

test('with no mission open the board holds none and asks nothing', () => {
    const requests = backend()
    show(null)
    expect(newest()).toBe('none')
    expect(requests).toEqual([])
})

test('a map made in one mission does not show in the next one opened', async () => {
    backend({ body: [overlay('120000')] }, { body: [] })
    const { rerender } = show(arizona())
    await waitFor(() => expect(newest()).toBe('20261125-120000_hiker'))
    rerender(
        <MissionContext value={{ mission: { ...arizona(), id: 'bear-creek' }, loadFailed: false, run: async () => '' }}>
            <ProbabilityProvider><Newest /></ProbabilityProvider>
        </MissionContext>,
    )
    expect(newest()).toBe('none')  // at once, before the backend has answered for the new mission
})

test('making a map sends the point, the kind of person and the hours, and the new map becomes the newest', async () => {
    const requests = backend({ body: [overlay('120000')] }, { body: overlay('150000') })
    show(arizona())
    await waitFor(() => expect(newest()).toBe('20261125-120000_hiker'))

    let answer: unknown
    await act(async () => { answer = await held.make(START_POINT) })

    expect(answer).toBe('')
    expect(requests[1]).toEqual({ address: '/api/spm/predict', method: 'POST', body: START_POINT })
    expect(newest()).toBe('20261125-150000_hiker')
})

test('when the model refuses, make answers with its reason and the map on the board stays', async () => {
    backend({ body: [overlay('120000')] }, { status: 422, body: { detail: 'terrain is incomplete: no trail/road file' } })
    show(arizona())
    await waitFor(() => expect(newest()).toBe('20261125-120000_hiker'))

    let answer: unknown
    await act(async () => { answer = await held.make(START_POINT) })

    expect(answer).toBe('terrain is incomplete: no trail/road file')
    expect(newest()).toBe('20261125-120000_hiker')
})
