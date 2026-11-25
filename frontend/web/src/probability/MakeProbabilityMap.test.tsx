import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import { ARIZONA07 } from '../waypoints/sample.ts'
import MakeProbabilityMap from './MakeProbabilityMap.tsx'
import { ProbabilityContext, type MapRequest, type ModelStatus } from './probability.ts'
import { board, READY } from './sample.ts'

afterEach(() => {
    cleanup()
    vi.unstubAllGlobals()
})

const START_POINT = ARIZONA07[1]  // the last known position

// The form's button on the Start point's card, with a pretend backend that answers the
// model's status, and a board whose make is the one given.
function show(status: ModelStatus | 'unreachable' = READY, make: (request: MapRequest) => Promise<string> = async () => '') {
    vi.stubGlobal('fetch', async () => {
        if (status === 'unreachable') throw new Error('Failed to fetch')
        return { ok: true, status: 200, statusText: '', json: async () => status }
    })
    const onMade = vi.fn()
    render(
        <ProbabilityContext value={board(null, make)}>
            <MakeProbabilityMap waypoint={START_POINT} onMade={onMade} />
        </ProbabilityContext>,
    )
    return onMade
}

// Presses Make Probability Map and waits for the form.
async function openForm() {
    fireEvent.click(screen.getByRole('button', { name: 'Make Probability Map' }))
    return await screen.findByRole('combobox', { name: 'Kind of person' }) as HTMLSelectElement
}

const hours = () => screen.getByRole('spinbutton', { name: 'Hours missing (optional)' }) as HTMLInputElement
const make = () => screen.getByRole('button', { name: 'Make Map' }) as HTMLButtonElement

test('at first there is only the button', () => {
    show()
    expect(screen.getByRole('button', { name: 'Make Probability Map' })).toBeTruthy()
    expect(screen.queryByRole('combobox')).toBeNull()
})

test('the form asks for the kind of person, from the kinds the model can draw, and the hours missing, left empty', async () => {
    show({ ...READY, models: { model_a: ['child_7_12', 'hiker'] } })
    const kind = await openForm()
    expect([...kind.options].map((option) => [option.value, option.textContent])).toEqual([['child_7_12', 'Child 7 12'], ['hiker', 'Hiker']])
    expect(hours().value).toBe('')
    expect(make().disabled).toBe(false)
})

test('Make Map sends the waypoint\'s place, the kind of person and the hours, then says the map is made', async () => {
    const sent: MapRequest[] = []
    const onMade = show(READY, async (request) => { sent.push(request); return '' })
    await openForm()
    fireEvent.change(hours(), { target: { value: '6.5' } })
    fireEvent.click(make())
    await waitFor(() => expect(onMade).toHaveBeenCalledOnce())
    expect(sent).toEqual([{ lon: -110.6762167, lat: 31.5057167, model: 'model_a', category: 'hiker', elapsed_h: 6.5 }])
    expect(screen.getByRole('status').textContent).toBe('Map made. It shows as the Probability heatmap layer.')
    expect(screen.queryByRole('combobox')).toBeNull()  // the form is put away
})

test('with the hours left empty the map is made with none', async () => {
    const sent: MapRequest[] = []
    show(READY, async (request) => { sent.push(request); return '' })
    await openForm()
    fireEvent.click(make())
    await waitFor(() => expect(sent).toHaveLength(1))
    expect(sent[0].elapsed_h).toBeNull()
})

test('while the model works the form says so, and its buttons are greyed', async () => {
    let finish = (_reason: string) => {}
    show(READY, () => new Promise((resolve) => { finish = resolve }))
    await openForm()
    fireEvent.click(make())
    expect((await screen.findByRole('status')).textContent).toBe('Making the map. This takes a few seconds.')
    expect(make().disabled).toBe(true)
    expect((screen.getByRole('button', { name: 'Cancel' }) as HTMLButtonElement).disabled).toBe(true)
    finish('')
    await waitFor(() => expect(screen.getByRole('status').textContent).toContain('Map made.'))
})

test('when the model refuses, the form says why and stays', async () => {
    const onMade = show(READY, async () => 'terrain is incomplete: no trail/road file (osm_lines*.gpkg) covers this window')
    await openForm()
    fireEvent.click(make())
    expect((await screen.findByRole('alert')).textContent).toBe('terrain is incomplete: no trail/road file (osm_lines*.gpkg) covers this window')
    expect(screen.getByRole('combobox', { name: 'Kind of person' })).toBeTruthy()
    expect(onMade).not.toHaveBeenCalled()
})

test.each(['-1', '721'])('hours of %s cannot be sent: Make Map is greyed and a line says what is allowed', async (typed) => {
    show()
    await openForm()
    fireEvent.change(hours(), { target: { value: typed } })
    expect(make().disabled).toBe(true)
    expect(screen.getByText('Hours missing is a number from 0 to 720.')).toBeTruthy()
})

test('when the model is not installed the form says so in place of its boxes', async () => {
    show({ available: false, detail: 'no Python at ml/spm/.venv/bin/python (install ml/spm with its geo and viz extras)', models: {} })
    fireEvent.click(screen.getByRole('button', { name: 'Make Probability Map' }))
    expect((await screen.findByRole('alert')).textContent).toBe(
        'The model is not available: no Python at ml/spm/.venv/bin/python (install ml/spm with its geo and viz extras)',
    )
    expect(screen.queryByRole('combobox')).toBeNull()
    expect(screen.queryByRole('button', { name: 'Make Map' })).toBeNull()
})

test('when the backend cannot be asked about the model the form says so', async () => {
    show('unreachable')
    fireEvent.click(screen.getByRole('button', { name: 'Make Probability Map' }))
    expect((await screen.findByRole('alert')).textContent).toBe('The model is not available: Failed to fetch')
})

test('Cancel puts the form away and leaves the button', async () => {
    show()
    await openForm()
    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }))
    expect(screen.queryByRole('combobox')).toBeNull()
    expect(screen.getByRole('button', { name: 'Make Probability Map' })).toBeTruthy()
})
