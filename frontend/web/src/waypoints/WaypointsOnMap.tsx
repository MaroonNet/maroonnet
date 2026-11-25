import type { Map as MapLibreMap } from 'maplibre-gl'
import { useEffect, useState } from 'react'
import { Marker } from 'react-map-gl/maplibre'
import { useMissionMap } from '../map/missionMap.ts'
import KindMarker from './KindMarker.tsx'
import { kindOf } from './kinds.ts'
import { useWaypoints, type Waypoint } from './waypoints.ts'

type Props = {
    selected: number[]                  // the ids of the selected waypoints; the one alone is drawn with a ring
    onPick?: (ids: number[]) => void    // given while a click on a waypoint picks it (the Select tool)
    hidden?: number | null              // a waypoint being edited, drawn by the editing's pin instead
}

// Two markers this close on screen, in pixels, cover each other: a marker is 30 across.
const SAME_SPOT = 20

// The waypoints on the map: each its kind's marker, centered on its place, with its name to
// the right. Waypoints on the same spot of the screen are a stack: one label counts them,
// and a click picks them all, so the card can ask which is meant. It is drawn inside the
// map (a child of MissionMap). The markers are page elements laid over the map, so they
// sit above the sectors.
function WaypointsOnMap({ selected, onPick, hidden = null }: Props) {
    const map = useMissionMap()
    const { waypoints } = useWaypoints()
    const shown = waypoints.filter((waypoint) => waypoint.id !== hidden)
    const ringed = selected.length === 1 ? selected[0] : null

    // How close two waypoints are on screen depends on the zoom, so the stacks are worked
    // out again each time the map zooms.
    const [, setZooms] = useState(0)
    useEffect(() => {
        if (!map) return
        const onZoom = () => setZooms((count) => count + 1)
        map.on('zoom', onZoom)
        return () => { map.off('zoom', onZoom) }
    }, [map])
    const stacks = map ? stacksOf(shown, map) : shown.map((waypoint) => [waypoint])

    return stacks.flatMap((stack) => stack.map((waypoint, place) => {
        // The last of a stack is drawn on top, and carries the stack's label.
        const label = place < stack.length - 1 ? '' : stack.length > 1 ? `${stack.length} waypoints` : waypoint.name
        return (
            <Marker
                key={waypoint.id}
                longitude={waypoint.lon}
                latitude={waypoint.lat}
                anchor="center"
                // While another tool is in use a click goes through the marker to the map.
                style={{ pointerEvents: onPick ? 'auto' : 'none', cursor: onPick ? 'pointer' : '' }}
                onClick={(event) => {
                    if (!onPick) return
                    event.originalEvent.stopPropagation()  // the click is not also a click on the sector under it
                    onPick(stack.map((one) => one.id))
                }}
            >
                {/* The marker is as big as its circle, so the circle sits on the place; the
                    label hangs off its right side. */}
                <div
                    title={`${waypoint.name} · ${kindOf(waypoint.kind).label}`}
                    aria-current={waypoint.id === ringed ? 'true' : undefined}
                    className="relative flex"
                >
                    <KindMarker kind={waypoint.kind} ringed={waypoint.id === ringed} />
                    {label && (
                        <span className="absolute top-1/2 left-full ml-1.5 -translate-y-1/2 font-sans text-body font-bold whitespace-nowrap text-ink [text-shadow:0_0_2px_#fff,0_0_2px_#fff,0_0_3px_#fff,0_0_3px_#fff]">
                            {label}
                        </span>
                    )}
                </div>
            </Marker>
        )
    }))
}

// The waypoints sorted into stacks: each joins the first stack whose first waypoint is on
// the same spot of the screen, or starts a stack of its own.
function stacksOf(waypoints: Waypoint[], map: MapLibreMap): Waypoint[][] {
    const stacks: { x: number, y: number, members: Waypoint[] }[] = []
    for (const waypoint of waypoints) {
        const { x, y } = map.project([waypoint.lon, waypoint.lat])
        const near = stacks.find((stack) => Math.hypot(stack.x - x, stack.y - y) < SAME_SPOT)
        if (near) near.members.push(waypoint)
        else stacks.push({ x, y, members: [waypoint] })
    }
    return stacks.map((stack) => stack.members)
}

export default WaypointsOnMap
