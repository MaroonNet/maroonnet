import { act, cleanup, fireEvent, render, screen } from '@testing-library/react'
import { useState } from 'react'
import { afterEach, expect, test, vi } from 'vitest'
import { SettingsContext, type Units } from '../settings/settings.ts'
import MeasureTool from './MeasureTool.tsx'

// A pretend map. It keeps the listeners the tool gives it, so a test can play the user:
// click(...) is a click on the map at a place, and move(...) is the pointer moving over it.
const map = vi.hoisted(() => {
    type Listener = (event: { lngLat: { lat: number, lng: number } }) => void
    const listeners: Record<string, Listener | undefined> = {}
    const canvas = { style: { cursor: '' } }
    return {
        listeners,
        canvas,
        on: (event: string, listener: Listener) => { listeners[event] = listener },
        off: (event: string) => { listeners[event] = undefined },
        getCanvas: () => canvas,
        doubleClickZoom: { enable: vi.fn(), disable: vi.fn() },
        click: (lat: number, lon: number) => listeners.click?.({ lngLat: { lat, lng: lon } }),
        move: (lat: number, lon: number) => listeners.mousemove?.({ lngLat: { lat, lng: lon } }),
    }
})
vi.mock('../map/missionMap.ts', () => ({ useMissionMap: () => map }))

// The map library's pieces for drawing on the map, as boxes that print what they were given.
vi.mock('react-map-gl/maplibre', () => ({
    Source: ({ data, children }: { data: unknown, children: unknown }) => <div data-testid="source">{JSON.stringify(data)}{children as never}</div>,
    Layer: () => null,
    Marker: ({ children }: { children: unknown }) => <div data-testid="label">{children as never}</div>,
}))

afterEach(() => {
    cleanup()
    vi.clearAllMocks()
})

function drawTool(units: Units = 'imperial') {
    function Screen() {
        const [hintSlot, setHintSlot] = useState<HTMLElement | null>(null)  // as App keeps it
        return (
            <SettingsContext value={{ settings: { units }, loadFailed: false, change: async () => false }}>
                <div ref={setHintSlot} />
                <MeasureTool hintSlot={hintSlot} />
            </SettingsContext>
        )
    }
    render(<Screen />)
}

const hint = () => screen.getByRole('status').textContent
const label = () => screen.queryByTestId('label')?.textContent
// The line on the map, as its list of [longitude, latitude] corners.
const line = () => JSON.parse(screen.getByTestId('source').firstChild!.textContent!).features[0].geometry.coordinates

// Two places a tenth of a degree of latitude apart: 11.1 km, or 6.9 miles, due north.
const START = [31.5, -110.7] as const
const END = [31.6, -110.7] as const

test('the tool first asks for the start point, and draws nothing', () => {
    drawTool()
    expect(hint()).toBe('Click the start point.')
    expect(screen.queryByTestId('source')).toBeNull()
    expect(label()).toBeUndefined()
})

test('after the first click the line follows the pointer, and the hint line shows the distance and bearing so far', () => {
    drawTool()
    act(() => map.click(...START))
    expect(hint()).toBe('Click the end point.')

    act(() => map.move(...END))
    expect(hint()).toBe('6.9 mi · 000°Click the end point.')
    expect(line()).toEqual([[-110.7, 31.5], [-110.7, 31.6]])
})

test('the second click fixes the line, and a label at its end shows the distance and the bearing from the first point', () => {
    drawTool()
    act(() => map.click(...START))
    act(() => map.click(...END))
    expect(label()).toBe('6.9 mi · 000°')

    act(() => map.move(31.9, -110.2))  // the pointer moving on changes nothing
    expect(label()).toBe('6.9 mi · 000°')
    expect(line()).toEqual([[-110.7, 31.5], [-110.7, 31.6]])
    expect(hint()).toContain('Click to measure again')
})

test('the label follows the Units setting, and the bearing is from true north', () => {
    drawTool('metric')
    act(() => map.click(...START))
    act(() => map.click(31.5, -110.6))  // due east
    expect(label()).toBe('9.5 km · 090°')
})

test('a third click starts a new measurement, and the old line goes', () => {
    drawTool()
    act(() => map.click(...START))
    act(() => map.click(...END))
    act(() => map.click(31.4, -110.5))
    expect(label()).toBeUndefined()
    expect(hint()).toBe('Click the end point.')
})

test('Escape clears the measurement', () => {
    drawTool()
    act(() => map.click(...START))
    act(() => map.click(...END))
    fireEvent.keyDown(document.body, { key: 'Escape' })
    expect(label()).toBeUndefined()
    expect(screen.queryByTestId('source')).toBeNull()
    expect(hint()).toBe('Click the start point.')
})

test('while the tool is picked the pointer is a crosshair and a double click does not zoom; leaving puts both back', () => {
    drawTool()
    expect(map.canvas.style.cursor).toBe('crosshair')
    expect(map.doubleClickZoom.disable).toHaveBeenCalledOnce()

    cleanup()
    expect(map.canvas.style.cursor).toBe('')
    expect(map.doubleClickZoom.enable).toHaveBeenCalledOnce()
    expect(map.listeners.click).toBeUndefined()
})
