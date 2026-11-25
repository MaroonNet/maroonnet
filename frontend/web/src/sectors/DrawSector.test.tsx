import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { useState } from 'react'
import { afterEach, expect, test, vi } from 'vitest'
import type { Bounds, Position } from '../map/geo.ts'
import { SearchAreaContext } from '../searchArea/searchArea.ts'
import { SettingsContext, type Units } from '../settings/settings.ts'
import DrawSector from './DrawSector.tsx'
import { SectorsContext } from './sectors.ts'

// The real drawing needs a real map. This stand-in keeps what the tool handed it, so a test
// can play the user: change(...) is the shape moving under the pointer, finish(...) is the
// shape drawn, and outside() is a rectangle let go wholly outside the search area.
type Listeners = { change: (corners: Position[]) => void, finish: (corners: Position[]) => void, outside: () => void }
const drawing = vi.hoisted(() => ({
    on: null as unknown as Listeners,
    area: null as unknown,
    discard: vi.fn(),
    stop: vi.fn(),
    map: {},  // the pretend map: the same one on every redraw, as the real one is
}))
vi.mock('../map/drawSector.ts', () => ({
    drawSector: (_map: unknown, area: unknown, on: Listeners) => {
        drawing.on = on
        drawing.area = area
        return { discard: drawing.discard, stop: drawing.stop }
    },
}))
vi.mock('../map/missionMap.ts', () => ({ useMissionMap: () => drawing.map }))

afterEach(() => {
    cleanup()
    vi.clearAllMocks()
})

const ARIZONA07_AREA: Bounds = { min_lat: 31.3926, min_lon: -110.8083, max_lat: 31.619, max_lon: -110.544 }
// Arizona07's S7, nine corners.
const S7: Position[] = [[31.510046, -110.679325], [31.513835, -110.679272], [31.515188, -110.676638], [31.515278, -110.672002],
    [31.513925, -110.668209], [31.510948, -110.667893], [31.509280, -110.671791], [31.510633, -110.675585], [31.510588, -110.677481]]
    .map(([lat, lon]) => ({ lat, lon }))
const SQUARE: Position[] = [{ lat: 31.5, lon: -110.7 }, { lat: 31.51, lon: -110.7 }, { lat: 31.51, lon: -110.69 }, { lat: 31.5, lon: -110.69 }]

// Draws the tool with the spot its hint line goes in. add is the sectors board's add: it
// answers with nothing when the sector was saved, and with the reason when it was not.
function drawTool(add = vi.fn(async (_corners: Position[]) => ''), units: Units = 'metric') {
    const onDone = vi.fn()
    function Screen() {
        const [hintSlot, setHintSlot] = useState<HTMLElement | null>(null)  // as App keeps it
        return (
            <SettingsContext value={{ settings: { units }, loadFailed: false, change: async () => false }}>
                <SearchAreaContext value={{ area: ARIZONA07_AREA, loadedFor: 'az07', save: async () => '' }}>
                    <SectorsContext value={{ sectors: [], loadedFor: 'az07', add }}>
                        <div ref={setHintSlot} />
                        <DrawSector hintSlot={hintSlot} onDone={onDone} />
                    </SectorsContext>
                </SearchAreaContext>
            </SettingsContext>
        )
    }
    render(<Screen />)
    return { add, onDone }
}
const hint = () => screen.getByRole('status').textContent
const card = () => screen.queryByRole('heading', { name: 'New Sector' })

test('the hint line says to drag, there is no card yet, and the drawing is kept to the search area', () => {
    drawTool()
    expect(hint()).toBe('Drag on the map to draw a sector.')
    expect(card()).toBeNull()
    expect(drawing.area).toEqual(ARIZONA07_AREA)
})

test('while the rectangle is dragged the hint line shows its area', () => {
    drawTool()
    act(() => drawing.on.change(S7))
    expect(hint()).toContain('0.55 km²')
    expect(card()).toBeNull()
})

test('a drawn sector opens the New Sector card with its points and area', () => {
    drawTool()
    act(() => drawing.on.finish(S7))
    expect(card()).toBeTruthy()
    expect(screen.getByText('Points').nextSibling?.textContent).toBe('9')
    expect(screen.getByText('Area').nextSibling?.textContent).toBe('0.55 km²')
    expect(hint()).toBe('0.55 km²Drag a corner to move it, or Save the sector.')  // the figure stays, as with the search area
})

test('the card follows the Units setting', () => {
    drawTool(undefined, 'imperial')
    act(() => drawing.on.finish(S7))
    expect(screen.getByText('Area').nextSibling?.textContent).toBe('0.21 mi²')
})

test('dragging a corner changes the figures on the card', () => {
    drawTool()
    act(() => drawing.on.finish(S7))
    act(() => drawing.on.change(SQUARE))
    expect(screen.getByText('Points').nextSibling?.textContent).toBe('4')
    expect(card()).toBeTruthy()
})

test('Save saves the corners and the tool is done', async () => {
    const { add, onDone } = drawTool()
    act(() => drawing.on.finish(S7))
    act(() => drawing.on.change(SQUARE))  // a corner was dragged before saving

    fireEvent.click(screen.getByRole('button', { name: 'Save' }))

    await waitFor(() => expect(onDone).toHaveBeenCalledOnce())
    expect(add).toHaveBeenCalledWith(SQUARE)
})

test('when the save is refused the card stays and says why', async () => {
    const { onDone } = drawTool(vi.fn(async () => 'This session is ended, so nothing in it can be changed.'))
    act(() => drawing.on.finish(S7))

    fireEvent.click(screen.getByRole('button', { name: 'Save' }))

    expect((await screen.findByRole('alert')).textContent).toBe('This session is ended, so nothing in it can be changed.')
    expect(card()).toBeTruthy()
    expect(onDone).not.toHaveBeenCalled()
})

test('Discard takes the sector away, saves nothing, and the tool stays ready for another drag', () => {
    const { add } = drawTool()
    act(() => drawing.on.finish(S7))

    fireEvent.click(screen.getByRole('button', { name: 'Discard' }))

    expect(drawing.discard).toHaveBeenCalledOnce()
    expect(card()).toBeNull()
    expect(hint()).toBe('Drag on the map to draw a sector.')
    expect(add).not.toHaveBeenCalled()
})

test('Escape discards too', () => {
    drawTool()
    act(() => drawing.on.finish(S7))

    fireEvent.keyDown(document.body, { key: 'Escape' })

    expect(drawing.discard).toHaveBeenCalledOnce()
    expect(card()).toBeNull()
})

test('a rectangle let go wholly outside the search area is not drawn, and the hint line says why', () => {
    drawTool()
    act(() => drawing.on.change(SQUARE))
    act(() => drawing.on.outside())
    expect(hint()).toBe('A sector must be inside the search area. Drag inside the dashed line.')
    expect(card()).toBeNull()
})

test('leaving the tool stops the drawing', () => {
    drawTool()
    cleanup()
    expect(drawing.stop).toHaveBeenCalledOnce()
})
