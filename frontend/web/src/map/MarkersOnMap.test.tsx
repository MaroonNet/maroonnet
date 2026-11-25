import { act, cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import type { CSSProperties, ReactNode } from 'react'
import { afterEach, expect, test, vi } from 'vitest'
import type { LayerChoice } from '../layers/missionLayers.ts'
import { PeopleContext } from '../people/people.ts'
import { RADIOS } from '../teams/sample.ts'
import { groupColor, NO_GROUP_COLOR } from '../teams/teamWords.ts'
import type { Radio } from '../teams/teams.ts'
import { ARIZONA07, board } from '../waypoints/sample.ts'
import { WaypointsContext, type Waypoint } from '../waypoints/waypoints.ts'
import MarkersOnMap from './MarkersOnMap.tsx'
import type { Stack } from './stacks.ts'

// The map library's marker, as a box at its place, noting which point of it is on the place.
// A press on it reaches the component as the library's own click does.
type MarkerProps = { longitude: number, latitude: number, anchor?: string, style?: CSSProperties, onClick?: (event: unknown) => void, children: ReactNode }
const stopped = vi.hoisted(() => ({ count: 0 }))
vi.mock('react-map-gl/maplibre', () => ({
    Marker: ({ longitude, latitude, anchor, style, onClick, children }: MarkerProps) => (
        <div
            data-testid="marker"
            data-place={`${latitude},${longitude}`}
            data-anchor={anchor}
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
vi.mock('./missionMap.ts', () => {
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

type Drawn = {
    waypoints?: Waypoint[]
    radios?: Radio[]
    team?: number | null        // the selected team
    waypoint?: number | null    // the selected waypoint
    onPick?: (stack: Stack) => void
    hidden?: number | null
    teamsLayer?: LayerChoice
    waypointsLayer?: LayerChoice
}

function draw({ waypoints = [], radios = [], team = null, waypoint = null, onPick, hidden = null, teamsLayer, waypointsLayer }: Drawn) {
    render(
        <PeopleContext value={{ roster: [], people: [], radios, groups: [], run: async () => '' }}>
            <WaypointsContext value={board(waypoints)}>
                <MarkersOnMap
                    selectedTeam={team}
                    selectedWaypoint={waypoint}
                    onPick={onPick}
                    hidden={hidden}
                    teamsLayer={teamsLayer}
                    waypointsLayer={waypointsLayer}
                />
            </WaypointsContext>
        </PeopleContext>,
    )
    return screen.queryAllByTestId('marker')
}

// The words beside a marker: a waypoint's name, or a stack's count.
const label = (marker: HTMLElement) => marker.querySelector('[data-label]')?.textContent ?? ''
const labels = () => screen.getAllByTestId('marker').map(label)

// A color as the pretend browser writes it back.
function written(color: string): string {
    const probe = document.createElement('span')
    probe.style.background = color
    return probe.style.background
}

// A team of one searcher, at a place of its own unless one is given.
function team(id: number, group_id: number | null, lat = 31.4 + id / 100, lon = -110.6): Radio {
    return {
        id, node_num: 100 + id, kind: 'searcher', group_id,
        people: [{ id: 50 + id, name: `Searcher ${id}`, placeholder: false }],
        last_position: { time: '2025-04-14T11:19:00Z', lat, lon, elevation: 1500 },
    }
}

// Waypoints

test('each waypoint is a marker at its place, with its name beside its kind\'s icon', () => {
    const markers = draw({ waypoints: ARIZONA07.slice(0, 5) })
    expect(markers.map(label)).toEqual(['Command post', 'Start point', 'LZ 1', 'Boot prints', 'Helicopter sighting'])
    expect(markers[3].dataset.place).toBe('31.5071259,-110.6693262')
    expect(within(markers[3]).getByTitle('Boot prints · Evidence')).toBeTruthy()
    expect(markers[3].querySelector('.tabler-icon-zoom-exclamation')).toBeTruthy()
})

test("a waypoint is a pin with its point on its place; a team's dot is centered on its place", () => {
    const markers = draw({ waypoints: ARIZONA07.slice(3, 4), radios: [team(1, 1)] })
    expect(markers.map((marker) => marker.dataset.anchor)).toEqual(['bottom', 'center'])
    expect(markers[0].querySelector('[data-outline]')).toBeTruthy()
    expect(markers[1].querySelector('[data-outline]')).toBeNull()
})

test('a click on a lone waypoint picks it, and the click does not reach the map under it', () => {
    const onPick = vi.fn()
    const markers = draw({ waypoints: ARIZONA07, onPick })
    fireEvent.click(markers[3])
    expect(onPick).toHaveBeenCalledWith({ teams: [], waypoints: [4] })
    expect(stopped.count).toBe(1)
})

test('a click where two waypoints sit on the same spot picks both', () => {
    const onPick = vi.fn()
    const markers = draw({ waypoints: ARIZONA07, onPick })
    fireEvent.click(markers[5])  // Subject found, about 4 m from the helicopter sighting
    expect(onPick).toHaveBeenCalledWith({ teams: [], waypoints: [5, 6] })
})

test('waypoints on the same spot share one label that counts them, so their names do not print over each other', () => {
    draw({ waypoints: ARIZONA07 })
    expect(labels()).toEqual(['Command post', 'Start point', 'LZ 1', 'Boot prints', '', '2 waypoints'])
})

test('zooming out brings more waypoints onto one spot, and the labels follow', () => {
    draw({ waypoints: ARIZONA07 })
    // A tenth of the scale: the command post and the start point, 14 px apart, are now one
    // stack. LZ 1 and the boot prints are clicked on their own but are within 75 px of it, so
    // they show no names. The finds are still 160 px from the boot prints.
    act(() => pretend.zoomTo(10_000))
    expect(labels()).toEqual(['', '2 waypoints', '', '', '', '2 waypoints'])
})

test('while another tool is in use a marker takes no clicks, so they reach the map', () => {
    const markers = draw({ waypoints: ARIZONA07, radios: [team(4, 2)] })
    for (const marker of markers) expect(marker.style.pointerEvents).toBe('none')
    fireEvent.click(markers[0])
    expect(stopped.count).toBe(0)
})

test('the selected waypoint is marked', () => {
    const markers = draw({ waypoints: ARIZONA07, waypoint: 4, onPick: () => {} })
    const current = markers.filter((marker) => marker.querySelector('[aria-current="true"]'))
    expect(current.map(label)).toEqual(['Boot prints'])
})

test('a waypoint being edited is not drawn; its pin is', () => {
    const markers = draw({ waypoints: ARIZONA07, hidden: 4 })
    expect(markers.map(label)).not.toContain('Boot prints')
    expect(markers).toHaveLength(5)
})

// Teams

test("each team is a dot at its newest position, in its group's color and grey for none, with a pill beside it naming its group and radio", () => {
    const markers = draw({ radios: [team(1, 1), team(4, null)] })
    expect(labels()).toEqual(['G1R1', 'R4'])
    expect(markers[0].dataset.place).toBe('31.41,-110.6')
    expect(within(markers[0]).getByText('G1').style.background).toBe(written(groupColor(1)))
    const colors = [...markers[1].querySelectorAll<HTMLElement>('[style]')].map((element) => element.style.background)
    expect(colors).toContain(written(NO_GROUP_COLOR))
    expect(within(markers[1]).getByTitle('Radio 4 · No group')).toBeTruthy()
})

test('only a team that has reported has a marker: not the command post radio, a relay, a radio with nobody, or a team with no position', () => {
    const markers = draw({ radios: RADIOS })  // radios 1, 2 and 7 are teams with a position
    expect(markers.map((marker) => marker.querySelector('[title]')!.getAttribute('title'))).toEqual(['Radio 1 · Group 1', 'Radio 2 · Group 1', 'Radio 7 · Group 2'])
})

test('a click on a lone team picks it, and the click does not reach the map under it', () => {
    const onPick = vi.fn()
    const markers = draw({ radios: [team(1, 1), team(4, null)], onPick })
    fireEvent.click(markers[1])
    expect(onPick).toHaveBeenCalledWith({ teams: [4], waypoints: [] })
    expect(stopped.count).toBe(1)
})

test('teams on the same spot share one label that counts them, in place of their pills, and a click picks them all', () => {
    const onPick = vi.fn()
    const markers = draw({ radios: RADIOS, onPick })  // all three at the same place
    expect(labels()).toEqual(['', '', '3 teams'])
    expect(screen.queryByText('G2')).toBeNull()
    fireEvent.click(markers[2])
    expect(onPick).toHaveBeenCalledWith({ teams: [1, 2, 7], waypoints: [] })
})

test('teams and waypoints on the same spot are one stack, and a click picks them all', () => {
    const onPick = vi.fn()
    // The sample's teams are about 5 m from the command post.
    const markers = draw({ waypoints: ARIZONA07.slice(0, 1), radios: RADIOS, onPick })
    expect(labels()).toEqual(['', '', '', '3 teams · 1 waypoint'])
    fireEvent.click(markers[0])
    expect(onPick).toHaveBeenCalledWith({ teams: [1, 2, 7], waypoints: [1] })
})

test('one team on one waypoint is counted in the singular', () => {
    draw({ waypoints: ARIZONA07.slice(0, 1), radios: RADIOS.slice(0, 1) })
    expect(labels()).toEqual(['', '1 team · 1 waypoint'])
})

// On the pretend map a ten-thousandth of a degree is 10 px.

test('teams 40 px apart are each clicked on their own, and show neither a count nor their pills', () => {
    const onPick = vi.fn()
    const markers = draw({ radios: [team(1, 1, 31.4, -110.6), team(2, 1, 31.4, -110.5996)], onPick })
    expect(labels()).toEqual(['', ''])
    fireEvent.click(markers[0])
    expect(onPick).toHaveBeenLastCalledWith({ teams: [1], waypoints: [] })
    fireEvent.click(markers[1])
    expect(onPick).toHaveBeenLastCalledWith({ teams: [2], waypoints: [] })
})

test('teams less than 25 px apart are one stack: one click picks both, and the top one carries their count', () => {
    const onPick = vi.fn()
    const markers = draw({ radios: [team(1, 1, 31.4, -110.6), team(2, 1, 31.4, -110.5998)], onPick })  // 20 px
    expect(labels()).toEqual(['', '2 teams'])
    fireEvent.click(markers[0])
    expect(onPick).toHaveBeenLastCalledWith({ teams: [1, 2], waypoints: [] })
})

test('a stack keeps its count among other markers, and a team clicked on its own beside it shows nothing', () => {
    // Teams 1 and 2 are 20 px apart; team 3 is 50 px past team 2.
    draw({ radios: [team(1, 1, 31.4, -110.6), team(2, 1, 31.4, -110.5998), team(3, 2, 31.4, -110.5993)] })
    expect(labels()).toEqual(['', '2 teams', ''])
})

test('teams 75 px or more apart each show their own pill', () => {
    draw({ radios: [team(1, 1, 31.4, -110.6), team(2, 1, 31.4, -110.5992)] })  // 80 px
    expect(labels()).toEqual(['G1R1', 'G1R2'])
})

// The Layers panel's two rows

const HIDDEN = { shown: false, opacity: 1 }

test('with the Team positions layer unticked only the waypoints are drawn, and a stack counts and picks only them', () => {
    const onPick = vi.fn()
    const markers = draw({ waypoints: ARIZONA07.slice(0, 1), radios: RADIOS, onPick, teamsLayer: HIDDEN })
    expect(labels()).toEqual(['Command post'])
    fireEvent.click(markers[0])
    expect(onPick).toHaveBeenCalledWith({ teams: [], waypoints: [1] })
})

test('with the Waypoints layer unticked only the teams are drawn', () => {
    draw({ waypoints: ARIZONA07, radios: RADIOS, waypointsLayer: HIDDEN })
    expect(labels()).toEqual(['', '', '3 teams'])
})

test("each marker is as strong as its own layer's opacity", () => {
    const markers = draw({
        waypoints: ARIZONA07.slice(2, 3), radios: [team(4, null)],
        teamsLayer: { shown: true, opacity: 0.5 }, waypointsLayer: { shown: true, opacity: 0.25 },
    })
    expect(markers.map((marker) => (marker.firstElementChild as HTMLElement).style.opacity)).toEqual(['0.25', '0.5'])
})

test('the selected team is marked', () => {
    const markers = draw({ radios: [team(1, 1), team(4, null)], team: 4, onPick: () => {} })
    const current = markers.filter((marker) => marker.querySelector('[aria-current="true"]'))
    expect(current.map((marker) => marker.textContent)).toEqual(['R4'])
})
