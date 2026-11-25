import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { useState } from 'react'
import { afterEach, expect, test, vi } from 'vitest'
import type { Bounds } from '../map/geo.ts'
import { SettingsContext, type Units } from '../settings/settings.ts'
import DrawSearchArea from './DrawSearchArea.tsx'
import SearchAreaOutline from './SearchAreaOutline.tsx'
import { SearchAreaContext, type SearchArea } from './searchArea.ts'

// The real drawing needs a real map. This stand-in keeps what the tool handed it, so a
// test can play the user: drag(...) is the pointer moving with the button held, and
// finish(...) is the button let go.
const drawing = vi.hoisted(() => ({
    drag: (_box: Bounds) => {},
    finish: (_box: Bounds) => {},
    clear: vi.fn(),
    stop: vi.fn(),
    map: {},  // the pretend map: the same one on every redraw, as the real one is
}))
vi.mock('../map/drawRectangle.ts', () => ({
    drawRectangle: (_map: unknown, on: { drag: (box: Bounds) => void, finish: (box: Bounds) => void }) => {
        drawing.drag = on.drag
        drawing.finish = on.finish
        return { clear: drawing.clear, stop: drawing.stop }
    },
}))
vi.mock('../map/missionMap.ts', () => ({ useMissionMap: () => drawing.map }))

// The map library's two pieces for drawing a shape, as boxes that print what they were given.
vi.mock('react-map-gl/maplibre', () => ({
    Source: ({ data, children }: { data: unknown, children: unknown }) => <div data-testid="source">{JSON.stringify(data)}{children as never}</div>,
    Layer: ({ type, paint }: { type: string, paint: unknown }) => <div data-testid="layer">{type} {JSON.stringify(paint)}</div>,
}))

afterEach(() => {
    cleanup()
    vi.clearAllMocks()
})

// Arizona07's search area: 25.1 by 25.2 km.
const ARIZONA07_AREA: SearchArea = { min_lat: 31.3926, min_lon: -110.8083, max_lat: 31.619, max_lon: -110.544 }

// Draws the tool with the spot its hint line goes in. save is the search area board's save:
// it answers with nothing when the area was saved, and with the reason when it was not.
function drawTool(save = vi.fn(async (_area: SearchArea) => ''), units: Units = 'imperial') {
    const onDone = vi.fn()
    function Screen() {
        const [hintSlot, setHintSlot] = useState<HTMLElement | null>(null)  // as App keeps it
        return (
            <SettingsContext value={{ settings: { units }, loadFailed: false, change: async () => false }}>
                <SearchAreaContext value={{ area: null, loadedFor: 'bc', save }}>
                    <div ref={setHintSlot} />
                    <DrawSearchArea hintSlot={hintSlot} onDone={onDone} />
                </SearchAreaContext>
            </SettingsContext>
        )
    }
    render(<Screen />)
    return { save, onDone }
}

test('the hint line says to drag, and there is no card yet', () => {
    drawTool()
    expect(screen.getByRole('status').textContent).toBe('Drag on the map to draw the search area.')
    expect(screen.queryByRole('heading', { name: 'New Search Area' })).toBeNull()
})

test('while the rectangle is dragged the hint line shows its size', () => {
    drawTool()
    act(() => drawing.drag(ARIZONA07_AREA))
    expect(screen.getByRole('status').textContent).toContain('15.6 mi × 15.6 mi')
    expect(screen.queryByRole('heading', { name: 'New Search Area' })).toBeNull()
})

test('a finished rectangle opens the New Search Area card with its width, height and area', () => {
    drawTool()
    act(() => drawing.finish(ARIZONA07_AREA))
    expect(screen.getByRole('heading', { name: 'New Search Area' })).toBeTruthy()
    expect(screen.getByText('Width').nextSibling?.textContent).toBe('15.6 mi')
    expect(screen.getByText('Height').nextSibling?.textContent).toBe('15.6 mi')
    expect(screen.getByText('Area').nextSibling?.textContent).toBe('243.55 mi²')
})

test('the card follows the Units setting', () => {
    drawTool(undefined, 'metric')
    act(() => drawing.finish(ARIZONA07_AREA))
    expect(screen.getByText('Width').nextSibling?.textContent).toBe('25.1 km')
    expect(screen.getByText('Height').nextSibling?.textContent).toBe('25.2 km')
    expect(screen.getByText('Area').nextSibling?.textContent).toBe('630.79 km²')
})

test('Apply saves the rectangle and the tool is done', async () => {
    const { save, onDone } = drawTool()
    act(() => drawing.finish(ARIZONA07_AREA))

    fireEvent.click(screen.getByRole('button', { name: 'Apply' }))

    await waitFor(() => expect(onDone).toHaveBeenCalledOnce())
    expect(save).toHaveBeenCalledWith(ARIZONA07_AREA)
})

test('when the save is refused the card stays and says why', async () => {
    const { onDone } = drawTool(vi.fn(async () => 'This session is paused, so nothing in it can be changed.'))
    act(() => drawing.finish(ARIZONA07_AREA))

    fireEvent.click(screen.getByRole('button', { name: 'Apply' }))

    expect((await screen.findByRole('alert')).textContent).toBe('This session is paused, so nothing in it can be changed.')
    expect(screen.getByRole('heading', { name: 'New Search Area' })).toBeTruthy()
    expect(onDone).not.toHaveBeenCalled()
})

test('Cancel takes the rectangle away and saves nothing', () => {
    const { save } = drawTool()
    act(() => drawing.finish(ARIZONA07_AREA))

    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }))

    expect(drawing.clear).toHaveBeenCalledOnce()
    expect(screen.queryByRole('heading', { name: 'New Search Area' })).toBeNull()
    expect(save).not.toHaveBeenCalled()
})

test('Escape cancels too', () => {
    const { save } = drawTool()
    act(() => drawing.finish(ARIZONA07_AREA))

    fireEvent.keyDown(document.body, { key: 'Escape' })

    expect(drawing.clear).toHaveBeenCalledOnce()
    expect(screen.queryByRole('heading', { name: 'New Search Area' })).toBeNull()
    expect(save).not.toHaveBeenCalled()
})

test('dragging again replaces the rectangle on the card', () => {
    drawTool()
    act(() => drawing.finish(ARIZONA07_AREA))
    act(() => drawing.drag({ min_lat: 31.5, min_lon: -110.7, max_lat: 31.51, max_lon: -110.69 }))
    expect(screen.queryByRole('heading', { name: 'New Search Area' })).toBeNull()
})

test('leaving the tool stops the drawing', () => {
    drawTool()
    cleanup()
    expect(drawing.stop).toHaveBeenCalledOnce()
})

test('the saved search area is drawn as a dashed line around its four corners', () => {
    render(
        <SearchAreaContext value={{ area: ARIZONA07_AREA, loadedFor: 'az07', save: async () => '' }}>
            <SearchAreaOutline />
        </SearchAreaContext>,
    )
    const shape = JSON.parse(screen.getByTestId('source').firstChild!.textContent!)
    // West and south first, round the corners, and back to the start.
    expect(shape.geometry.coordinates).toEqual([
        [-110.8083, 31.3926], [-110.544, 31.3926], [-110.544, 31.619], [-110.8083, 31.619], [-110.8083, 31.3926],
    ])
    expect(screen.getByTestId('layer').textContent).toContain('line-dasharray')
})

test('with no search area nothing is drawn', () => {
    render(<SearchAreaOutline />)
    expect(screen.queryByTestId('source')).toBeNull()
})
