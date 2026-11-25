import { useEffect, useState } from 'react'
import { Marker } from 'react-map-gl/maplibre'
import { SHOWN, type LayerChoice } from '../layers/missionLayers.ts'
import { usePeople } from '../people/people.ts'
import { groupLabel, radioLabel } from '../people/peopleWords.ts'
import TeamMarker from '../teams/TeamMarker.tsx'
import { teamsOnMap } from '../teams/teamWords.ts'
import type { Radio } from '../teams/teams.ts'
import KindMarker from '../waypoints/KindMarker.tsx'
import { kindOf } from '../waypoints/kinds.ts'
import { useWaypoints, type Waypoint } from '../waypoints/waypoints.ts'
import { useMissionMap } from './missionMap.ts'
import { stacksOf, stackWords, type Stack } from './stacks.ts'

type Props = {
    selectedTeam: number | null         // the radio of the selected team, drawn with a ring
    selectedWaypoint: number | null     // the id of the selected waypoint, drawn with a ring
    onPick?: (stack: Stack) => void     // given while a click on a marker picks it (the Select tool)
    hidden?: number | null              // a waypoint being edited, drawn by the editing's pin instead
    // The Layers panel's choices for Team positions and for Waypoints: shown or not, and how solid.
    teamsLayer?: LayerChoice
    waypointsLayer?: LayerChoice
}

// One thing with a marker: a waypoint at its place, or a team at its newest position.
type Placed = { lat: number, lon: number, waypoint?: Waypoint, team?: Radio }

// The markers on the map. A waypoint is its kind's marker, centered on its place, with its
// name to the right. A team is a circle in its group's color at its radio's newest
// position, with its short name inside. Markers on the same spot of the screen, of either
// sort, are one stack: one label counts them, and a click picks them all, so a card can ask
// which is meant. It is drawn inside the map (a child of MissionMap). The markers are page
// elements laid over the map, so they sit above the sectors and the tracks. A sort unticked
// in the Layers panel has no markers, so a stack counts and picks only what shows.
function MarkersOnMap({ selectedTeam, selectedWaypoint, onPick, hidden = null, teamsLayer = SHOWN, waypointsLayer = SHOWN }: Props) {
    const map = useMissionMap()
    const { waypoints } = useWaypoints()
    const { radios } = usePeople()
    const shownWaypoints = waypointsLayer.shown ? waypoints.filter((waypoint) => waypoint.id !== hidden) : []
    const shownTeams = teamsLayer.shown ? teamsOnMap(radios) : []
    // Waypoints first, so in a stack of both a team is drawn on top.
    const placed: Placed[] = [
        ...shownWaypoints.map((waypoint) => ({ lat: waypoint.lat, lon: waypoint.lon, waypoint })),
        ...shownTeams.map((team) => ({ lat: team.last_position!.lat, lon: team.last_position!.lon, team })),
    ]

    // How close two markers are on screen depends on the zoom, so the stacks are worked out
    // again each time the map zooms.
    const [, setZooms] = useState(0)
    useEffect(() => {
        if (!map) return
        const onZoom = () => setZooms((count) => count + 1)
        map.on('zoom', onZoom)
        return () => { map.off('zoom', onZoom) }
    }, [map])
    const stacks = map ? stacksOf(placed, map) : placed.map((one) => [one])

    return stacks.flatMap((stack) => {
        const picked: Stack = {
            teams: stack.flatMap((one) => one.team ? [one.team.id] : []),
            waypoints: stack.flatMap((one) => one.waypoint ? [one.waypoint.id] : []),
        }
        return stack.map((one, place) => {
            const { waypoint, team } = one
            // The last of a stack is drawn on top, and carries the stack's label. A lone
            // waypoint's label is its name; a lone team's name is inside its circle.
            const top = place === stack.length - 1
            const label = !top ? '' : stack.length > 1 ? stackWords(picked.teams.length, picked.waypoints.length) : waypoint?.name ?? ''
            const ringed = waypoint ? waypoint.id === selectedWaypoint : team!.id === selectedTeam
            return (
                <Marker
                    key={waypoint ? `waypoint-${waypoint.id}` : `team-${team!.id}`}
                    longitude={one.lon}
                    latitude={one.lat}
                    anchor="center"
                    // While another tool is in use a click goes through the marker to the map.
                    style={{ pointerEvents: onPick ? 'auto' : 'none', cursor: onPick ? 'pointer' : '' }}
                    onClick={(event) => {
                        if (!onPick) return
                        event.originalEvent.stopPropagation()  // the click is not also a click on the sector under it
                        onPick(picked)
                    }}
                >
                    {/* The marker is as big as its circle, so the circle sits on the place; the
                        label hangs off its right side. */}
                    <div
                        title={waypoint ? `${waypoint.name} · ${kindOf(waypoint.kind).label}` : `${radioLabel(team!.id)} · ${groupLabel(team!.group_id)}`}
                        aria-current={ringed ? 'true' : undefined}
                        style={{ opacity: (waypoint ? waypointsLayer : teamsLayer).opacity }}
                        className="relative flex"
                    >
                        {waypoint ? <KindMarker kind={waypoint.kind} ringed={ringed} /> : <TeamMarker radio={team!} ringed={ringed} />}
                        {label && (
                            <span data-label className="absolute top-1/2 left-full ml-1.5 -translate-y-1/2 font-sans text-body font-bold whitespace-nowrap text-ink [text-shadow:0_0_2px_#fff,0_0_2px_#fff,0_0_3px_#fff,0_0_3px_#fff]">
                                {label}
                            </span>
                        )}
                    </div>
                </Marker>
            )
        })
    })
}

export default MarkersOnMap
