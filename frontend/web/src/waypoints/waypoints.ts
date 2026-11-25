import { createContext, useContext } from 'react'
import { ask } from '../mission/mission.ts'

// A waypoint as the backend answers it (backend/waypoints/routes.py).
export type Waypoint = {
    id: number
    kind: string                // a kind's code, such as "hazard" (kinds.ts)
    lat: number
    lon: number
    name: string
    description: string | null  // sent to teams with the waypoint, once sending is built
    note: string | null         // kept at the command post only
    time: string                // UTC; when the thing happened or was seen
    created_time: string        // UTC; when this row was saved
    radio_id: number | null     // the radio that reported it, or none when the commander placed it
}

// What the commander sets on a waypoint: the form's boxes, and where the pin is.
export type Placing = Pick<Waypoint, 'kind' | 'lat' | 'lon' | 'name'> & { description: string, note: string }

export const loadWaypoints = () => ask<Waypoint[]>('/api/mission/waypoints')
export const addWaypoint = (placing: Placing) => ask<Waypoint>('/api/mission/waypoints', 'POST', placing)
// A change closes the waypoint's row and adds a new one, so the answer has a new id.
export const changeWaypoint = (id: number, placing: Placing) => ask<Waypoint>(`/api/mission/waypoints/${id}`, 'PUT', placing)
export const removeWaypoint = (id: number) => ask<null>(`/api/mission/waypoints/${id}`, 'DELETE')

// The board: the waypoints on the open mission's map, kept in one place that any component
// can read. add and change answer with the waypoint as saved, or with the reason as text
// when it was not saved; remove answers with nothing when it worked, and with the reason
// when it did not. The board changes only when a change worked.
export type WaypointsBoard = {
    waypoints: Waypoint[]       // in the order they were saved; none while no mission is open
    loadedFor: string | null    // the id of the mission the waypoints were read for; none until read
    add: (placing: Placing) => Promise<Waypoint | string>
    change: (id: number, placing: Placing) => Promise<Waypoint | string>
    remove: (id: number) => Promise<string>
}

// A component drawn with no WaypointsProvider above it, as in a test of one component,
// reads this board: no waypoints, and nothing can be saved.
const NO_BOARD = 'There is no waypoints board.'
export const WaypointsContext = createContext<WaypointsBoard>({
    waypoints: [],
    loadedFor: null,
    add: async () => NO_BOARD,
    change: async () => NO_BOARD,
    remove: async () => NO_BOARD,
})

// What a component calls to read the board.
export function useWaypoints(): WaypointsBoard {
    return useContext(WaypointsContext)
}
