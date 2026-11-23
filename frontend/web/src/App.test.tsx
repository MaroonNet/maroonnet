import { act, cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import App from './App.tsx'

// A pretend MapLibre map. It records zoom presses, and a test can move it to another zoom.
// vi.hoisted makes it before the stand-ins below, which use it.
const fakeMap = vi.hoisted(() => {
    let zoom = 11
    let onMove = () => {}
    return {
        zoomIn: vi.fn(),
        zoomOut: vi.fn(),
        getZoom: () => zoom,
        getMinZoom: () => 0,
        getMaxZoom: () => 17,
        getCenter: () => ({ lat: 39.74 }),  // Denver
        on: (_event: string, listener: () => void) => { onMove = listener },
        off: () => { onMove = () => {} },
        moveToZoom(newZoom: number) { zoom = newZoom; onMove() },
    }
})

// The real map needs the backend and a real browser, so the tests draw a box in its place.
// The box prints the lists the map was handed, so a test can read which layers it was told
// to hide, and it hands the pretend map up as the real one does when it is ready.
vi.mock('./map/MissionMap.tsx', async () => {
    const { useEffect } = await import('react')
    type Props = { hidden: string[], pickedUses: string[], onMap: (map: unknown) => void }
    function StandInMap({ onMap, ...lists }: Props) {
        useEffect(() => onMap(fakeMap), [onMap])
        return <div data-testid="map">{JSON.stringify(lists)}</div>
    }
    return { default: StandInMap }
})

// The style comes from the backend too. This one lists two layer groups and two trail uses.
vi.mock('./map/mapStyle.ts', () => ({
    styleError: '',
    style: {
        metadata: {
            groups: [{ id: 'trails', label: 'Trails' }, { id: 'contours', label: 'Contours' }],
            trail_uses: [
                { id: 'hiking', label: 'Hiking allowed', filter: ['==', ['get', 'foot'], 'yes'] },
                { id: 'horse', label: 'Horse allowed', filter: ['==', ['get', 'horse'], 'yes'] },
            ],
        },
    },
}))

function handedToMap(): { hidden: string[], pickedUses: string[] } {
    return JSON.parse(screen.getByTestId('map').textContent!)
}

function openLayers() {
    fireEvent.click(screen.getByRole('button', { name: 'Layers' }))
}

// Between tests: clear the page, forget the recorded zoom presses, and put the map back.
afterEach(() => {
    cleanup()
    vi.clearAllMocks()
    fakeMap.moveToZoom(11)
})

test('the rail shows the Mission block, the nine buttons and Settings', () => {
    render(<App />)
    const labels = ['Groups & Teams', 'People', 'Sectors', 'Area', 'Alerts', 'Mesh', 'Layers', 'Maps', 'AAR']
    for (const label of labels) {
        expect(screen.getByRole('button', { name: label })).toBeTruthy()
    }
    expect(screen.getByRole('button', { name: /Mission/ })).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Settings' })).toBeTruthy()
})

test('pressing Layers opens a panel titled "Map Layers"', () => {
    render(<App />)
    fireEvent.click(screen.getByRole('button', { name: 'Layers' }))
    expect(screen.getByRole('heading', { name: 'Map Layers' })).toBeTruthy()
})

test('pressing Layers again closes the panel', () => {
    render(<App />)
    fireEvent.click(screen.getByRole('button', { name: 'Layers' }))
    fireEvent.click(screen.getByRole('button', { name: 'Layers' }))
    expect(screen.queryByRole('heading', { name: 'Map Layers' })).toBeNull()
})

test('the × button closes the panel', () => {
    render(<App />)
    fireEvent.click(screen.getByRole('button', { name: 'Layers' }))
    fireEvent.click(screen.getByRole('button', { name: 'Close panel' }))
    expect(screen.queryByRole('heading', { name: 'Map Layers' })).toBeNull()
})

test('a greyed button opens nothing and says "Not available yet"', () => {
    render(<App />)
    const people = screen.getByRole('button', { name: 'People' })
    expect(people.title).toBe('Not available yet')
    expect(people.getAttribute('aria-disabled')).toBe('true')
    fireEvent.click(people)
    expect(screen.queryByRole('heading')).toBeNull()
})

test('unticking a layer group in the Layers panel tells the map to hide it', () => {
    render(<App />)
    openLayers()
    fireEvent.click(screen.getByRole('checkbox', { name: 'Contours' }))
    expect(handedToMap().hidden).toEqual(['contours'])
    fireEvent.click(screen.getByRole('checkbox', { name: 'Contours' }))
    expect(handedToMap().hidden).toEqual([])
})

test('the Layers panel lists every layer group ticked, and the trail uses unticked', () => {
    render(<App />)
    openLayers()
    expect(screen.getByRole('heading', { name: 'Basemap' })).toBeTruthy()
    const ticked = (name: string) => (screen.getByRole('checkbox', { name }) as HTMLInputElement).checked
    expect(ticked('Trails')).toBe(true)
    expect(ticked('Contours')).toBe(true)
    expect(ticked('Hiking allowed')).toBe(false)
    expect(ticked('Horse allowed')).toBe(false)
})

test('ticking a trail use tells the map to narrow the trails to it', () => {
    render(<App />)
    openLayers()
    fireEvent.click(screen.getByRole('checkbox', { name: 'Horse allowed' }))
    expect(handedToMap().pickedUses).toEqual(['horse'])
})

test('the choices are kept while the panel is closed', () => {
    render(<App />)
    openLayers()
    fireEvent.click(screen.getByRole('checkbox', { name: 'Contours' }))
    fireEvent.click(screen.getByRole('button', { name: 'Close panel' }))
    expect(handedToMap().hidden).toEqual(['contours'])
    openLayers()
    expect((screen.getByRole('checkbox', { name: 'Contours' }) as HTMLInputElement).checked).toBe(false)
})

test('the toolbar shows the Select tool, picked', () => {
    render(<App />)
    expect(screen.getByRole('button', { name: 'Select' }).getAttribute('aria-pressed')).toBe('true')
})

test('hovering the Select tool shows its name and key, and leaving hides them', () => {
    render(<App />)
    const select = screen.getByRole('button', { name: 'Select' })
    fireEvent.mouseEnter(select)
    expect(screen.getByRole('tooltip').textContent).toBe('SelectV')
    fireEvent.mouseLeave(select)
    expect(screen.queryByRole('tooltip')).toBeNull()
})

test('keyboard focus on the Select tool shows the same tooltip', () => {
    render(<App />)
    const select = screen.getByRole('button', { name: 'Select' })
    fireEvent.focus(select)
    expect(screen.getByRole('tooltip').textContent).toBe('SelectV')
    fireEvent.blur(select)
    expect(screen.queryByRole('tooltip')).toBeNull()
})

test('the zoom buttons zoom the map in and out', () => {
    render(<App />)
    fireEvent.click(screen.getByRole('button', { name: 'Zoom in' }))
    expect(fakeMap.zoomIn).toHaveBeenCalledOnce()
    expect(fakeMap.zoomOut).not.toHaveBeenCalled()
    fireEvent.click(screen.getByRole('button', { name: 'Zoom out' }))
    expect(fakeMap.zoomOut).toHaveBeenCalledOnce()
})

test('a zoom button is greyed out and does nothing at its zoom limit', () => {
    render(<App />)
    const greyed = (name: string) => screen.getByRole('button', { name }).getAttribute('aria-disabled') === 'true'
    expect(greyed('Zoom in')).toBe(false)
    expect(greyed('Zoom out')).toBe(false)

    act(() => fakeMap.moveToZoom(17))  // the deepest zoom
    expect(greyed('Zoom in')).toBe(true)
    expect(greyed('Zoom out')).toBe(false)
    fireEvent.click(screen.getByRole('button', { name: 'Zoom in' }))
    expect(fakeMap.zoomIn).not.toHaveBeenCalled()

    act(() => fakeMap.moveToZoom(0))  // the widest zoom
    expect(greyed('Zoom in')).toBe(false)
    expect(greyed('Zoom out')).toBe(true)
    fireEvent.click(screen.getByRole('button', { name: 'Zoom out' }))
    expect(fakeMap.zoomOut).not.toHaveBeenCalled()
})

test('the scale bar shows a round distance for the map, and follows the map when it moves', () => {
    render(<App />)
    // Denver at zoom 11: a pixel covers 29.4 m, so 3.1 miles fit in the bar's 170 pixels.
    expect(screen.getByTitle('Map scale').textContent).toBe('3 mi')
    // Two zooms in, a quarter as much fits: 0.78 of a mile.
    act(() => fakeMap.moveToZoom(13))
    expect(screen.getByTitle('Map scale').textContent).toBe('0.5 mi')
})

test('the legend button opens the legend in its place, and the legend folds back to the button', () => {
    render(<App />)
    fireEvent.click(screen.getByRole('button', { name: 'Show legend' }))
    expect(screen.getByRole('heading', { name: 'Legend' })).toBeTruthy()
    expect(screen.queryByRole('button', { name: 'Show legend' })).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: 'Collapse legend' }))
    expect(screen.queryByRole('heading', { name: 'Legend' })).toBeNull()
    expect(screen.getByRole('button', { name: 'Show legend' })).toBeTruthy()
})
