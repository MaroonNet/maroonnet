import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { useState } from 'react'
import { afterEach, expect, test, vi } from 'vitest'
import type { Position } from '../map/geo.ts'
import PlaceWaypoint from './PlaceWaypoint.tsx'
import { ARIZONA07, board, waypoint } from './sample.ts'
import { WaypointsContext, type Placing, type Waypoint, type WaypointsBoard } from './waypoints.ts'

// The real pin needs a real map. This stand-in keeps what the tool handed it, so a test can
// play the user: pin.on.move(...) is a click on the map, or the pin dragged to a place.
const pin = vi.hoisted(() => ({
    on: null as unknown as { move: (position: Position) => void },
    start: undefined as Position | undefined,
    clear: vi.fn(),
    stop: vi.fn(),
    map: {},
}))
vi.mock('../map/dropPin.ts', () => ({
    dropPin: (_map: unknown, _element: unknown, on: typeof pin.on, start?: Position) => {
        pin.on = on
        pin.start = start
        return { clear: pin.clear, stop: pin.stop }
    },
}))
vi.mock('../map/missionMap.ts', () => ({ useMissionMap: () => pin.map }))

afterEach(() => {
    cleanup()
    vi.clearAllMocks()
})

const SPOT: Position = { lat: 31.5072, lon: -110.669 }

// Draws the tool with the spot its hint line goes in. editing: the waypoint being edited.
function drawTool(changes: Partial<WaypointsBoard> = {}, editing?: Waypoint, waypoints = ARIZONA07) {
    const onDone = vi.fn()
    function Page() {
        const [hintSlot, setHintSlot] = useState<HTMLElement | null>(null)
        return (
            <WaypointsContext value={board(waypoints, changes)}>
                <div ref={setHintSlot} />
                <PlaceWaypoint hintSlot={hintSlot} editing={editing} onDone={onDone} />
            </WaypointsContext>
        )
    }
    render(<Page />)
    return onDone
}

const click = (position: Position) => act(() => pin.on.move(position))
const box = (name: string) => screen.getByRole('textbox', { name }) as HTMLInputElement
const kind = () => screen.getByRole('combobox', { name: 'Kind' }) as HTMLSelectElement
const type = (name: string, text: string) => fireEvent.change(box(name), { target: { value: text } })
const save = () => screen.getByRole('button', { name: 'Save' }) as HTMLButtonElement

test('the tool starts with a hint and no card', () => {
    drawTool()
    expect(screen.getByRole('status').textContent).toBe('Click the map to drop a waypoint.')
    expect(screen.queryByRole('heading')).toBeNull()
})

test('a click on the map opens the New Waypoint card at that place, as Other, already named', () => {
    drawTool()
    click(SPOT)
    expect(screen.getByRole('heading', { name: 'New Waypoint' })).toBeTruthy()
    expect(screen.getByText('31.5072 N 110.6690 W')).toBeTruthy()
    expect(kind().value).toBe('other')
    expect(box('Name').value).toBe('Other 1')
    expect(screen.getByRole('status').textContent).toBe('Drag the pin or click the map to move it. Then Save the waypoint.')
})

test('the name follows the kind until something is typed in it', () => {
    drawTool()
    click(SPOT)
    fireEvent.change(kind(), { target: { value: 'find' } })
    expect(box('Name').value).toBe('Find 3')  // Arizona07 has two finds
    type('Name', 'Glove')
    fireEvent.change(kind(), { target: { value: 'evidence' } })
    expect(box('Name').value).toBe('Glove')
})

test('the kind list offers the ten kinds', () => {
    drawTool()
    click(SPOT)
    expect([...kind().options].map((option) => option.textContent)).toEqual([
        'Command post', 'Last known position', 'Point last seen', 'Evidence', 'Hazard', 'Landing zone', 'Find',
        'Relay', 'Meeting point', 'Other',
    ])
})

test('the description counts its bytes against 100, and Save is greyed past the limit', () => {
    drawTool()
    click(SPOT)
    expect(screen.getByText('0 / 100')).toBeTruthy()
    type('Description (sent to teams)', 'Cañon rim')  // nine letters, ten bytes
    expect(screen.getByText('10 / 100')).toBeTruthy()
    expect(save().disabled).toBe(false)
    type('Description (sent to teams)', 'x'.repeat(101))
    expect(screen.getByText('101 / 100')).toBeTruthy()
    expect(save().disabled).toBe(true)
})

test('a waypoint cannot be saved with no name, or with one over 30 bytes', () => {
    drawTool()
    click(SPOT)
    type('Name', '  ')
    expect(save().disabled).toBe(true)
    type('Name', 'x'.repeat(31))
    expect(screen.getByText('31 / 30')).toBeTruthy()
    expect(save().disabled).toBe(true)
    type('Name', 'x'.repeat(30))
    expect(save().disabled).toBe(false)
})

test('the Send to list is greyed, since sending is not built', () => {
    drawTool()
    click(SPOT)
    const sendTo = screen.getByRole('combobox', { name: 'Send to' }) as HTMLSelectElement
    expect(sendTo.disabled).toBe(true)
    expect(sendTo.title).toBe('Not available yet')
})

test('Save saves the waypoint where the pin is, with what was typed, and the tool is done', async () => {
    const add = vi.fn(async (_placing: Placing) => waypoint(7, 'hazard', 'Mine shaft') as Waypoint | string)
    const onDone = drawTool({ add })
    click(SPOT)
    click({ lat: 31.508, lon: -110.67 })  // the pin was dragged
    fireEvent.change(kind(), { target: { value: 'hazard' } })
    type('Name', 'Mine shaft')
    type('Description (sent to teams)', 'Open shaft, unfenced')
    type('Note (command post only)', 'Told by the ranger')
    fireEvent.click(save())

    await waitFor(() => expect(onDone).toHaveBeenCalled())
    expect(add).toHaveBeenCalledWith({
        kind: 'hazard', lat: 31.508, lon: -110.67, name: 'Mine shaft', description: 'Open shaft, unfenced', note: 'Told by the ranger',
    })
})

test('a save that is refused shows why, and the card stays', async () => {
    const onDone = drawTool({ add: async () => 'This session is paused, so nothing in it can be changed.' })
    click(SPOT)
    fireEvent.click(save())
    expect((await screen.findByRole('alert')).textContent).toBe('This session is paused, so nothing in it can be changed.')
    expect(onDone).not.toHaveBeenCalled()
    expect(screen.getByRole('heading', { name: 'New Waypoint' })).toBeTruthy()
})

test('Discard takes the pin and the card away, and the tool waits for another click', () => {
    drawTool()
    click(SPOT)
    type('Name', 'Glove')
    fireEvent.click(screen.getByRole('button', { name: 'Discard' }))
    expect(pin.clear).toHaveBeenCalled()
    expect(screen.queryByRole('heading')).toBeNull()
    expect(screen.getByRole('status').textContent).toBe('Click the map to drop a waypoint.')
    click(SPOT)
    expect(box('Name').value).toBe('Other 1')  // what was typed is gone
})

test('Escape discards too', () => {
    drawTool()
    click(SPOT)
    fireEvent.keyDown(window, { key: 'Escape' })
    expect(screen.queryByRole('heading')).toBeNull()
})

test('the pin goes when the tool does', () => {
    drawTool()
    cleanup()
    expect(pin.stop).toHaveBeenCalled()
})

// Editing

const HELICOPTER = ARIZONA07[4]

test('editing opens the card with the waypoint\'s facts, and the pin where the waypoint is', () => {
    drawTool({}, HELICOPTER)
    expect(screen.getByRole('heading', { name: 'Edit Waypoint' })).toBeTruthy()
    expect(pin.start).toEqual({ lat: 31.51, lon: -110.6533 })
    expect(kind().value).toBe('find')
    expect(box('Name').value).toBe('Helicopter sighting')
    expect(box('Description (sent to teams)').value).toBe('Heat signature on FLIR, not yet confirmed on the ground')
    expect(box('Note (command post only)').value).toBe('Reported by the Border Patrol helicopter')
})

test('an edited waypoint keeps its name when its kind changes', () => {
    drawTool({}, HELICOPTER)
    fireEvent.change(kind(), { target: { value: 'evidence' } })
    expect(box('Name').value).toBe('Helicopter sighting')
})

test('Save sends the change, and answers with the waypoint that took its place', async () => {
    const replaced = waypoint(7, 'find', 'Helicopter sighting')
    const change = vi.fn(async (_id: number, _placing: Placing) => replaced as Waypoint | string)
    const onDone = drawTool({ change }, HELICOPTER)
    click(SPOT)  // moved
    type('Note (command post only)', '')
    fireEvent.click(save())

    await waitFor(() => expect(onDone).toHaveBeenCalledWith(replaced))
    expect(change).toHaveBeenCalledWith(5, {
        kind: 'find', lat: 31.5072, lon: -110.669, name: 'Helicopter sighting',
        description: 'Heat signature on FLIR, not yet confirmed on the ground', note: '',
    })
})

test('Cancel ends the editing with nothing saved', () => {
    const change = vi.fn(async () => 'never')
    const onDone = drawTool({ change }, HELICOPTER)
    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }))
    expect(onDone).toHaveBeenCalledWith()
    expect(change).not.toHaveBeenCalled()
})
