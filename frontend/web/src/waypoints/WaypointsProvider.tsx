import { useEffect, useState, type ReactNode } from 'react'
import { sendError } from '../diagnostics/errorLog.ts'
import { useMission } from '../mission/mission.ts'
import {
    addWaypoint, changeWaypoint, loadWaypoints, removeWaypoint, WaypointsContext, type Placing, type Waypoint,
} from './waypoints.ts'

// Waypoints as they were read, and the mission they were read for.
type Read = { missionId: string, waypoints: Waypoint[] }

// Puts the waypoints board above the app. It asks the backend for the waypoints each time
// another mission is opened, and again when the open mission's session changes, since a new
// session's file holds its own copy. It holds none while no mission is open.
function WaypointsProvider({ children }: { children: ReactNode }) {
    const mission = useMission().mission
    const missionId = mission?.id
    const session = mission?.session
    const [read, setRead] = useState<Read | null>(null)

    useEffect(() => {
        if (!missionId) return
        let overtaken = false  // something else was opened before this answer arrived
        loadWaypoints().then((waypoints) => {
            if (!overtaken) setRead({ missionId, waypoints })
        }).catch((error) => sendError('mission', error))
        return () => { overtaken = true }
    }, [missionId, session])

    // Sends one change, then reads every waypoint again: a change gives a waypoint a new
    // id, and a new command post takes the old one off the map. Answers with what the
    // backend sent back, or with the reason as text when the change was refused.
    async function sendThenRead<Answer>(send: () => Promise<Answer>): Promise<Answer | string> {
        if (!missionId) return 'No mission is open.'
        try {
            const answer = await send()
            const waypoints = await loadWaypoints()
            setRead({ missionId, waypoints })
            return answer
        } catch (error) {
            return error instanceof Error ? error.message : String(error)
        }
    }
    const add = (placing: Placing) => sendThenRead(() => addWaypoint(placing))
    const change = (id: number, placing: Placing) => sendThenRead(() => changeWaypoint(id, placing))
    const remove = async (id: number) => await sendThenRead(() => removeWaypoint(id)) ?? ''

    // What was read for an earlier mission is not this mission's waypoints.
    const current = read && read.missionId === missionId ? read : null
    const waypoints = current?.waypoints ?? []
    const loadedFor = current?.missionId ?? null
    return <WaypointsContext value={{ waypoints, loadedFor, add, change, remove }}>{children}</WaypointsContext>
}

export default WaypointsProvider
