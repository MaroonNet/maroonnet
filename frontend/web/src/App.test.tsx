import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import App from './App.tsx'
import { MissionContext, type OpenMission } from './mission/mission.ts'
import { SearchAreaContext, type SearchArea } from './searchArea/searchArea.ts'
import SettingsProvider from './settings/SettingsProvider.tsx'

// A pretend MapLibre map. It records zoom presses, and a test can move it to another zoom.
// vi.hoisted makes it before the stand-ins below, which use it.
const fakeMap = vi.hoisted(() => {
    let zoom = 11
    let onMove = () => {}
    return {
        zoomIn: vi.fn(),
        zoomOut: vi.fn(),
        fitBounds: vi.fn(),  // opening a mission with a search area moves the map over it
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
// to hide.
vi.mock('./map/MissionMap.tsx', () => {
    type Props = { hidden: string[], pickedUses: string[] }
    function StandInMap({ hidden, pickedUses }: Props) {
        return <div data-testid="map">{JSON.stringify({ hidden, pickedUses })}</div>
    }
    return { default: StandInMap }
})

// The pieces outside the map read it from the shared board. Here the board holds the pretend map.
vi.mock('./map/missionMap.ts', () => ({ useMissionMap: () => fakeMap }))

// Drawing needs a real map too, so a tool that draws is handed a drawing that does nothing.
vi.mock('./map/drawRectangle.ts', () => ({ drawRectangle: () => ({ clear() {}, stop() {} }) }))
vi.mock('./map/drawSector.ts', () => ({ drawSector: () => ({ discard() {}, stop() {}, edit() {} }) }))
vi.mock('./map/drawCustomShape.ts', () => ({
    drawCustomShape: () => ({ undo() {}, redo() {}, close() {}, discard() {}, stop() {} }),
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

// Between tests: clear the page, forget the recorded zoom presses, take away any pretend
// backend, and put the map back.
afterEach(() => {
    cleanup()
    vi.clearAllMocks()
    vi.unstubAllGlobals()
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

test('pressing Sectors opens the Sectors panel', () => {
    render(<App />)
    fireEvent.click(screen.getByRole('button', { name: 'Sectors' }))
    expect(screen.getByRole('heading', { name: 'Sectors' })).toBeTruthy()
    expect(screen.getByText('No mission is open.')).toBeTruthy()
})

test('pressing Area opens the Search Area panel', () => {
    render(<App />)
    fireEvent.click(screen.getByRole('button', { name: 'Area' }))
    expect(screen.getByRole('heading', { name: 'Search Area' })).toBeTruthy()
    expect(screen.getByText('No mission is open.')).toBeTruthy()
})

test('a greyed button opens nothing and says "Not available yet"', () => {
    render(<App />)
    const alerts = screen.getByRole('button', { name: 'Alerts' })
    expect(alerts.title).toBe('Not available yet')
    expect(alerts.getAttribute('aria-disabled')).toBe('true')
    fireEvent.click(alerts)
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

test('the Draw Search Area tool is greyed until a mission is open', () => {
    render(<App />)  // no mission board above it, so no mission is open
    const tool = screen.getByRole('button', { name: 'Draw Search Area' })
    expect(tool.getAttribute('aria-disabled')).toBe('true')
    fireEvent.click(tool)
    expect(screen.getByRole('button', { name: 'Select' }).getAttribute('aria-pressed')).toBe('true')
    expect(screen.queryByRole('status')).toBeNull()  // no hint line: the tool did not start
})

test('with a mission open, picking Draw Search Area starts the tool, and its hint line shows under the toolbar', () => {
    const mission: OpenMission = {
        id: 'bc', name: 'Bear Creek', time_zone: 'America/Denver', status: 'planning', session: 1,
        start_time: null, end_time: null, sessions: [], asks_to_continue: false,
    }
    render(<MissionContext value={{ mission, loadFailed: false, run: async () => '' }}><App /></MissionContext>)

    fireEvent.click(screen.getByRole('button', { name: 'Draw Search Area' }))

    expect(screen.getByRole('button', { name: 'Draw Search Area' }).getAttribute('aria-pressed')).toBe('true')
    expect(screen.getByRole('status').textContent).toBe('Drag on the map to draw the search area.')
})

const BEAR_CREEK: OpenMission = {
    id: 'bc', name: 'Bear Creek', time_zone: 'America/Denver', status: 'planning', session: 1,
    start_time: null, end_time: null, sessions: [], asks_to_continue: false,
}

// Draws the app with Bear Creek open, and with a search area when one is given.
function withBearCreek(area: SearchArea | null) {
    render(
        <MissionContext value={{ mission: BEAR_CREEK, loadFailed: false, run: async () => '' }}>
            <SearchAreaContext value={{ area, loadedFor: 'bc', save: async () => '' }}>
                <App />
            </SearchAreaContext>
        </MissionContext>,
    )
}

function tooltipOf(name: string): string {
    fireEvent.mouseEnter(screen.getByRole('button', { name }))
    return screen.getByRole('tooltip').textContent!
}

test('the Draw Sector tool is greyed until a mission is open', () => {
    render(<App />)
    expect(screen.getByRole('button', { name: 'Draw Sector' }).getAttribute('aria-disabled')).toBe('true')
    expect(tooltipOf('Draw Sector')).toBe('Draw SectorOpen a mission first')
})

test('with a mission open and no search area, the Draw Sector tool is still greyed', () => {
    withBearCreek(null)
    const tool = screen.getByRole('button', { name: 'Draw Sector' })
    expect(tool.getAttribute('aria-disabled')).toBe('true')
    expect(tooltipOf('Draw Sector')).toBe('Draw SectorDraw a search area first')
    fireEvent.click(tool)
    expect(screen.queryByRole('status')).toBeNull()  // the tool did not start
})

test('with a search area, picking Draw Sector starts the tool, and its hint line shows under the toolbar', () => {
    withBearCreek({ min_lat: 39.9, min_lon: -105.7, max_lat: 40.1, max_lon: -105.5 })

    fireEvent.click(screen.getByRole('button', { name: 'Draw Sector' }))

    expect(screen.getByRole('button', { name: 'Draw Sector' }).getAttribute('aria-pressed')).toBe('true')
    expect(screen.getByRole('status').textContent).toBe('Drag on the map to draw a rectangle. Right-click the tool for a custom shape.')
})

test('picking Custom shape from the Draw Sector menu starts a custom shape, and the tool keeps that shape', () => {
    withBearCreek({ min_lat: 39.9, min_lon: -105.7, max_lat: 40.1, max_lon: -105.5 })

    fireEvent.contextMenu(screen.getByRole('button', { name: 'Draw Sector' }))
    fireEvent.click(screen.getByRole('menuitemradio', { name: 'Custom shape' }))

    expect(screen.getByRole('status').textContent).toBe('Click the map to drop the first point.')
    expect(screen.getByRole('button', { name: 'Undo' })).toBeTruthy()  // in the toolbar while the shape is drawn

    // Leaving the tool and picking it again starts the shape last picked.
    fireEvent.click(screen.getByRole('button', { name: 'Select' }))
    fireEvent.click(screen.getByRole('button', { name: 'Draw Sector' }))
    expect(screen.getByRole('status').textContent).toBe('Click the map to drop the first point.')
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

test('pressing Settings opens the Settings panel, with the two unit choices and miles and feet picked', () => {
    render(<App />)
    fireEvent.click(screen.getByRole('button', { name: 'Settings' }))
    expect(screen.getByRole('heading', { name: 'Settings' })).toBeTruthy()
    expect(screen.getByRole('heading', { name: 'Units' })).toBeTruthy()
    const picked = (name: string) => (screen.getByRole('radio', { name }) as HTMLInputElement).checked
    expect(picked('Miles and feet')).toBe(true)
    expect(picked('Kilometers and meters')).toBe(false)
})

test('one panel is open at a time: opening Settings closes Layers', () => {
    render(<App />)
    openLayers()
    fireEvent.click(screen.getByRole('button', { name: 'Settings' }))
    expect(screen.getByRole('heading', { name: 'Settings' })).toBeTruthy()
    expect(screen.queryByRole('heading', { name: 'Map Layers' })).toBeNull()
})

// The tests below draw the app as main.tsx does, inside the settings board, with a pretend
// backend answering the settings routes.

function jsonAnswer(body: unknown, status = 200): Response {
    return new Response(JSON.stringify(body), { status, headers: { 'content-type': 'application/json' } })
}

// Stands in for the backend's settings routes. saved is what its settings file holds.
// The list it returns fills with each change the web app sends.
function pretendBackend(saved: { units: string }, fail: { reads?: boolean, saves?: boolean } = {}) {
    const changesSent: unknown[] = []
    vi.stubGlobal('fetch', vi.fn(async (address: string, request?: RequestInit) => {
        if (address !== '/api/settings') return new Response(null, { status: 204 })  // the error log
        if (!request?.method) return fail.reads ? jsonAnswer({}, 500) : jsonAnswer(saved)
        changesSent.push({ method: request.method, body: JSON.parse(request.body as string) })
        if (fail.saves) return jsonAnswer({}, 500)
        Object.assign(saved, JSON.parse(request.body as string))
        return jsonAnswer(saved)
    }))
    return changesSent
}

async function openSettingsOnTheBoard() {
    render(<SettingsProvider><App /></SettingsProvider>)
    fireEvent.click(await screen.findByRole('button', { name: 'Settings' }))  // waits for the frame
}

function picked(name: string): boolean {
    return (screen.getByRole('radio', { name }) as HTMLInputElement).checked
}

test('the screen waits for the settings before it draws', async () => {
    let answer!: (response: Response) => void
    vi.stubGlobal('fetch', vi.fn(() => new Promise<Response>((resolve) => { answer = resolve })))
    render(<SettingsProvider><App /></SettingsProvider>)
    expect(screen.queryByRole('button', { name: 'Layers' })).toBeNull()

    await act(async () => answer(jsonAnswer({ units: 'metric' })))
    expect(screen.getByRole('button', { name: 'Layers' })).toBeTruthy()
})

test('the Settings panel shows the saved choice', async () => {
    pretendBackend({ units: 'metric' })
    await openSettingsOnTheBoard()
    expect(picked('Kilometers and meters')).toBe(true)
    expect(picked('Miles and feet')).toBe(false)
})

test('picking a unit choice sends only that setting, and the panel switches once the backend has saved it', async () => {
    const changesSent = pretendBackend({ units: 'imperial' })
    await openSettingsOnTheBoard()

    fireEvent.click(screen.getByRole('radio', { name: 'Kilometers and meters' }))
    expect(picked('Miles and feet')).toBe(true)  // not yet: the backend has not answered

    await waitFor(() => expect(picked('Kilometers and meters')).toBe(true))
    expect(changesSent).toEqual([{ method: 'PATCH', body: { units: 'metric' } }])
})

test('if a change cannot be saved, nothing switches and the panel says so', async () => {
    pretendBackend({ units: 'imperial' }, { saves: true })
    await openSettingsOnTheBoard()

    fireEvent.click(screen.getByRole('radio', { name: 'Kilometers and meters' }))

    expect((await screen.findByRole('alert')).textContent).toBe('The change could not be saved.')
    expect(picked('Miles and feet')).toBe(true)
})

test('a change that saves clears the note left by one that did not', async () => {
    const backend = { units: 'imperial' }
    pretendBackend(backend, { saves: true })
    await openSettingsOnTheBoard()
    fireEvent.click(screen.getByRole('radio', { name: 'Kilometers and meters' }))
    await screen.findByRole('alert')

    pretendBackend(backend)  // the backend can save again
    fireEvent.click(screen.getByRole('radio', { name: 'Kilometers and meters' }))

    await waitFor(() => expect(picked('Kilometers and meters')).toBe(true))
    expect(screen.queryByRole('alert')).toBeNull()
})

test('the scale bar follows the Units setting', async () => {
    pretendBackend({ units: 'imperial' })
    await openSettingsOnTheBoard()
    // Denver at zoom 11: 3.1 miles, or 5.0 kilometers, fit in the bar's 170 pixels.
    expect(screen.getByTitle('Map scale').textContent).toBe('3 mi')

    fireEvent.click(screen.getByRole('radio', { name: 'Kilometers and meters' }))

    await waitFor(() => expect(screen.getByTitle('Map scale').textContent).toBe('3 km'))
})

test('if the settings cannot be read, the frame draws with the starting values and the panel says so', async () => {
    pretendBackend({ units: 'metric' }, { reads: true })
    await openSettingsOnTheBoard()

    expect(picked('Miles and feet')).toBe(true)
    expect(screen.getByText('The settings could not be loaded, so the starting values are shown.')).toBeTruthy()
})
