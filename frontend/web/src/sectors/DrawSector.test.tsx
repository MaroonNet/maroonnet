import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { useState } from 'react'
import { afterEach, expect, test, vi } from 'vitest'
import type { Bounds, Position } from '../map/geo.ts'
import { SearchAreaContext } from '../searchArea/searchArea.ts'
import { SettingsContext, type Units } from '../settings/settings.ts'
import type { SectorShape } from '../map/drawSector.ts'
import DrawSector from './DrawSector.tsx'
import { NO_LIFE } from './sample.ts'
import { SectorsContext } from './sectors.ts'

// The real drawing needs a real map. These stand-ins keep what the tool handed them, so a
// test can play the user.
// drawSector: change(...) is the shape moving under the pointer, finish(...) is a rectangle
// drawn, and outside() is a rectangle let go wholly outside the search area. edit(...) is
// the tool handing it a closed custom shape, whose corners can then be dragged.
type Listeners = { change: (corners: Position[]) => void, finish: (corners: Position[]) => void, outside: () => void, full: () => void }
const drawing = vi.hoisted(() => ({
    on: null as unknown as Listeners,
    area: null as unknown,
    shape: '',
    discard: vi.fn(),
    stop: vi.fn(),
    edit: vi.fn(),
    map: {},  // the pretend map: the same one on every redraw, as the real one is
}))
vi.mock('../map/drawSector.ts', () => ({
    drawSector: (_map: unknown, area: unknown, shape: string, on: Listeners) => {
        drawing.on = on
        drawing.area = area
        drawing.shape = shape
        return { discard: drawing.discard, stop: drawing.stop, edit: drawing.edit }
    },
}))
// drawCustomShape: draft(...) is the shape after a click, an Undo or a Redo; finish(...) is
// the shape closed.
type Draft = { count: number, canUndo: boolean, canRedo: boolean, refused: 'full' | 'crosses' | 'too-few' | null }
type CustomListeners = { draft: (draft: Draft) => void, finish: (corners: Position[]) => void }
const custom = vi.hoisted(() => ({
    on: null as unknown as CustomListeners,
    started: 0,
    undo: vi.fn(), redo: vi.fn(), close: vi.fn(), discard: vi.fn(), stop: vi.fn(),
}))
vi.mock('../map/drawCustomShape.ts', () => ({
    drawCustomShape: (_map: unknown, _area: unknown, on: CustomListeners) => {
        custom.on = on
        custom.started += 1
        return { undo: custom.undo, redo: custom.redo, close: custom.close, discard: custom.discard, stop: custom.stop }
    },
}))
vi.mock('../map/missionMap.ts', () => ({ useMissionMap: () => drawing.map }))

afterEach(() => {
    cleanup()
    vi.clearAllMocks()
    custom.started = 0
})

const ARIZONA07_AREA: Bounds = { min_lat: 31.3926, min_lon: -110.8083, max_lat: 31.619, max_lon: -110.544 }
// Arizona07's S7, nine corners.
const S7: Position[] = [[31.510046, -110.679325], [31.513835, -110.679272], [31.515188, -110.676638], [31.515278, -110.672002],
    [31.513925, -110.668209], [31.510948, -110.667893], [31.509280, -110.671791], [31.510633, -110.675585], [31.510588, -110.677481]]
    .map(([lat, lon]) => ({ lat, lon }))
const SQUARE: Position[] = [{ lat: 31.5, lon: -110.7 }, { lat: 31.51, lon: -110.7 }, { lat: 31.51, lon: -110.69 }, { lat: 31.5, lon: -110.69 }]

// Draws the tool with the spots its hint line and its toolbar buttons go in. add is the
// sectors board's add: it answers with nothing when the sector was saved, and with the
// reason when it was not.
function drawTool(add = vi.fn(async (_corners: Position[]) => ''), units: Units = 'metric', shape: SectorShape = 'rectangle') {
    const onDone = vi.fn()
    function Screen() {
        const [hintSlot, setHintSlot] = useState<HTMLElement | null>(null)  // as App keeps them
        const [toolSlot, setToolSlot] = useState<HTMLElement | null>(null)
        return (
            <SettingsContext value={{ settings: { units }, loadFailed: false, change: async () => false }}>
                <SearchAreaContext value={{ area: ARIZONA07_AREA, loadedFor: 'az07', save: async () => '' }}>
                    <SectorsContext value={{ sectors: [], loadedFor: 'az07', add, changeShape: async () => '', remove: async () => '', ...NO_LIFE }}>
                        <div ref={setToolSlot} />
                        <div ref={setHintSlot} />
                        <DrawSector shape={shape} hintSlot={hintSlot} toolSlot={toolSlot} onDone={onDone} />
                    </SectorsContext>
                </SearchAreaContext>
            </SettingsContext>
        )
    }
    render(<Screen />)
    return { add, onDone }
}
const drawCustom = (add?: (corners: Position[]) => Promise<string>) => drawTool(add && vi.fn(add), 'metric', 'custom')
const draft = (count: number, refused: Draft['refused'] = null, canRedo = false): Draft => ({ count, canUndo: count > 0, canRedo, refused })
const hint = () => screen.getByRole('status').textContent
const card = () => screen.queryByRole('heading', { name: 'New Sector' })

const RECTANGLE_HINT = 'Drag on the map to draw a rectangle. Right-click the tool for a custom shape.'
const EDIT_HINT = "Drag a corner to move it, or a side's middle to add a corner. Then Save the sector."

test('the hint line says to drag, there is no card yet, and the drawing is kept to the search area', () => {
    drawTool()
    expect(hint()).toBe(RECTANGLE_HINT)
    expect(card()).toBeNull()
    expect(drawing.area).toEqual(ARIZONA07_AREA)
    expect(drawing.shape).toBe('rectangle')
    expect(custom.started).toBe(0)  // no click-by-click drawing for a rectangle
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
    expect(hint()).toBe(`0.55 km²${EDIT_HINT}`)  // the figure stays, as with the search area
})

test("a corner added from a side's middle past the 24th is refused, and the hint line says so", () => {
    drawTool()
    act(() => drawing.on.finish(S7))
    act(() => drawing.on.full())
    expect(hint()).toBe('0.55 km²A sector has at most 24 corners.')
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
    expect(hint()).toBe(RECTANGLE_HINT)
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

// A custom shape, drawn one click at a time.

test('a custom shape: the hint line counts the corners against the 24 allowed and says what to do next', () => {
    drawCustom()
    expect(custom.started).toBe(1)
    expect(drawing.shape).toBe('custom')
    expect(hint()).toBe('Click the map to drop the first point.')

    act(() => custom.on.draft(draft(2)))
    expect(hint()).toBe('2 of 24Keep clicking to add points. Backspace removes the last one.')

    act(() => custom.on.draft(draft(12)))
    expect(hint()).toBe('12 of 24Click the first point, double-click, or press Enter to close the sector.')
})

test('a 25th corner is refused, and the hint line says to close the shape or remove a point', () => {
    drawCustom()
    act(() => custom.on.draft(draft(24, 'full')))
    expect(hint()).toBe('24 of 24A sector has at most 24 corners. Close the shape, or remove a point.')
})

test('a click that would make sides cross is refused, and the hint line says why', () => {
    drawCustom()
    act(() => custom.on.draft(draft(5, 'crosses')))
    expect(hint()).toBe('5 of 24Sides cannot cross.')
})

test('closing with fewer than three corners is refused, and the hint line says why', () => {
    drawCustom()
    act(() => custom.on.draft(draft(2, 'too-few')))
    expect(hint()).toBe('2 of 24A sector needs at least 3 corners.')
})

test('Undo and Redo show on the toolbar while a custom shape is drawn, greyed when there is nothing to undo or redo', () => {
    drawCustom()
    const undo = screen.getByRole('button', { name: 'Undo' }), redo = screen.getByRole('button', { name: 'Redo' })
    expect([undo.getAttribute('aria-disabled'), redo.getAttribute('aria-disabled')]).toEqual(['true', 'true'])

    act(() => custom.on.draft(draft(4, null, true)))
    expect([undo.getAttribute('aria-disabled'), redo.getAttribute('aria-disabled')]).toEqual([null, null])

    fireEvent.click(undo)
    fireEvent.click(redo)
    expect(custom.undo).toHaveBeenCalledOnce()
    expect(custom.redo).toHaveBeenCalledOnce()
})

test('a rectangle has no Undo or Redo', () => {
    drawTool()
    expect(screen.queryByRole('button', { name: 'Undo' })).toBeNull()
})

test('Backspace and Ctrl+Z undo, Ctrl+Shift+Z redoes, and Enter closes the shape', () => {
    drawCustom()
    act(() => custom.on.draft(draft(4, null, true)))

    fireEvent.keyDown(document.body, { key: 'Backspace' })
    fireEvent.keyDown(document.body, { key: 'z', ctrlKey: true })
    fireEvent.keyDown(document.body, { key: 'z', metaKey: true })  // Cmd on a Mac
    fireEvent.keyDown(document.body, { key: 'Z', ctrlKey: true, shiftKey: true })
    fireEvent.keyDown(document.body, { key: 'Enter' })

    expect(custom.undo).toHaveBeenCalledTimes(3)
    expect(custom.redo).toHaveBeenCalledOnce()
    expect(custom.close).toHaveBeenCalledOnce()
})

test('a closed shape gets draggable corners and the New Sector card; Undo and Redo go', () => {
    drawCustom()
    act(() => custom.on.draft(draft(9)))

    act(() => custom.on.finish(S7))

    expect(drawing.edit).toHaveBeenCalledWith(S7)
    expect(card()).toBeTruthy()
    expect(screen.getByText('Points').nextSibling?.textContent).toBe('9')
    expect(hint()).toBe(`0.55 km²${EDIT_HINT}`)
    expect(screen.queryByRole('button', { name: 'Undo' })).toBeNull()
})

test('a closed custom shape is saved like a rectangle', async () => {
    const { add, onDone } = drawTool(undefined, 'metric', 'custom')
    act(() => custom.on.finish(S7))

    fireEvent.click(screen.getByRole('button', { name: 'Save' }))

    await waitFor(() => expect(onDone).toHaveBeenCalledOnce())
    expect(add).toHaveBeenCalledWith(S7)
})

test('Discard takes a closed custom shape away and starts the clicking again', () => {
    drawCustom()
    act(() => custom.on.finish(S7))

    fireEvent.click(screen.getByRole('button', { name: 'Discard' }))

    expect(drawing.discard).toHaveBeenCalledOnce()
    expect(custom.discard).toHaveBeenCalledOnce()
    expect(card()).toBeNull()
    expect(hint()).toBe('Click the map to drop the first point.')
    expect(screen.getByRole('button', { name: 'Undo' })).toBeTruthy()
})

test('leaving a custom shape stops both drawings', () => {
    drawCustom()
    cleanup()
    expect(custom.stop).toHaveBeenCalledOnce()
    expect(drawing.stop).toHaveBeenCalledOnce()
})
