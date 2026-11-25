import { act, cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import type { CSSProperties, ReactNode } from 'react'
import { afterEach, expect, test, vi } from 'vitest'
import { ARIZONA07, board } from './sample.ts'
import { WaypointsContext, type Waypoint } from './waypoints.ts'
import WaypointsOnMap from './WaypointsOnMap.tsx'

// The map library's marker, as a box at its place. A press on it reaches the component as
// the library's own click does.
type MarkerProps = { longitude: number, latitude: number, style?: CSSProperties, onClick?: (event: unknown) => void, children: ReactNode }
const stopped = vi.hoisted(() => ({ count: 0 }))
vi.mock('react-map-gl/maplibre', () => ({
    Marker: ({ longitude, latitude, style, onClick, children }: MarkerProps) => (
        <div
            data-testid="marker"
            data-place={`${latitude},${longitude}`}
            style={style}
            onClick={() => onClick?.({ originalEvent: { stopPropagation() { stopped.count += 1 } } })}
        >
            {children}
        </div>
    ),
}))

// A pretend map on which a degree is 100,000 pixels, so a meter is about a pixel. A test
// zooms it out with pretend.zoomTo(...), which tells the listener the component left.
const pretend = vi.hoisted(() => ({
    scale: 100_000,
    onZoom: null as (() => void) | null,
    zoomTo(scale: number) {
        this.scale = scale
        this.onZoom?.()
    },
}))
vi.mock('../map/missionMap.ts', () => {
    const map = {
        project: ([lon, lat]: [number, number]) => ({ x: lon * pretend.scale, y: lat * pretend.scale }),
        on: (_event: string, listener: () => void) => { pretend.onZoom = listener },
        off: () => { pretend.onZoom = null },
    }
    return { useMissionMap: () => map }
})

afterEach(() => {
    cleanup()
    stopped.count = 0
    pretend.scale = 100_000
})

function draw(waypoints: Waypoint[], selected: number[] = [], onPick?: (ids: number[]) => void, hidden: number | null = null) {
    render(
        <WaypointsContext value={board(waypoints)}>
            <WaypointsOnMap selected={selected} onPick={onPick} hidden={hidden} />
        </WaypointsContext>,
    )
    return screen.queryAllByTestId('marker')
}

test('each waypoint is a marker at its place, with its name beside its kind\'s icon', () => {
    const markers = draw(ARIZONA07.slice(0, 5))
    expect(markers.map((marker) => marker.textContent)).toEqual([
        'Command post', 'Start point', 'LZ 1', 'Boot prints', 'Helicopter sighting',
    ])
    expect(markers[3].dataset.place).toBe('31.5071259,-110.6693262')
    expect(within(markers[3]).getByTitle('Boot prints · Evidence')).toBeTruthy()
    expect(markers[3].querySelector('svg')).toBeTruthy()
})

test('a click on a lone waypoint picks it, and the click does not reach the map under it', () => {
    const onPick = vi.fn()
    const markers = draw(ARIZONA07, [], onPick)
    fireEvent.click(markers[3])
    expect(onPick).toHaveBeenCalledWith([4])
    expect(stopped.count).toBe(1)
})

test('a click where two waypoints sit on the same spot picks both', () => {
    const onPick = vi.fn()
    const markers = draw(ARIZONA07, [], onPick)
    fireEvent.click(markers[5])  // Subject found, about 4 m from the helicopter sighting
    expect(onPick).toHaveBeenCalledWith([5, 6])
})

test('waypoints on the same spot share one label that counts them, so their names do not print over each other', () => {
    const markers = draw(ARIZONA07)
    expect(markers.map((marker) => marker.textContent)).toEqual([
        'Command post', 'Start point', 'LZ 1', 'Boot prints', '', '2 waypoints',
    ])
})

test('zooming out brings more waypoints onto one spot, and the labels follow', () => {
    draw(ARIZONA07)
    // A tenth of the scale: the command post and the start point, 140 m apart, now touch.
    act(() => pretend.zoomTo(10_000))
    expect(screen.getAllByTestId('marker').map((marker) => marker.textContent)).toEqual([
        '', '2 waypoints', 'LZ 1', 'Boot prints', '', '2 waypoints',
    ])
})

test('while another tool is in use a marker takes no clicks, so they reach the map', () => {
    const markers = draw(ARIZONA07)
    expect(markers[0].style.pointerEvents).toBe('none')
    fireEvent.click(markers[0])
    expect(stopped.count).toBe(0)
})

test('the selected waypoint is marked', () => {
    const markers = draw(ARIZONA07, [4], () => {})
    const current = markers.filter((marker) => marker.querySelector('[aria-current="true"]'))
    expect(current.map((marker) => marker.textContent)).toEqual(['Boot prints'])
})

test('a waypoint being edited is not drawn; its pin is', () => {
    const markers = draw(ARIZONA07, [], undefined, 4)
    expect(markers.map((marker) => marker.textContent)).not.toContain('Boot prints')
    expect(markers).toHaveLength(5)
})
