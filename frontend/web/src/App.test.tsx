import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import App from './App.tsx'

// The real map needs the backend and a real browser, so the tests draw a box in its place.
// The box prints what the map was handed, so a test can read which layers it was told to hide.
vi.mock('./map/MissionMap.tsx', () => ({
    default: (props: object) => <div data-testid="map">{JSON.stringify(props)}</div>,
}))

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

afterEach(cleanup)  // clear the page between tests

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
