import { useEffect, useState, type ReactNode } from 'react'
import { sendError } from '../diagnostics/errorLog.ts'
import { useMission } from '../mission/mission.ts'
import { loadTracks, TracksContext, type Track } from './tracks.ts'

// Tracks as they were read, and the mission and session they were read for.
type Read = { missionId: string, session: number, tracks: Track[] }

// Puts the tracks board above the app. It asks the backend for the tracks once each time
// another mission is opened, and again when the open mission's session changes, since a new
// session's file starts with no positions. It is thousands of points, so it is not read
// again after that: nothing in the app adds a position.
function TracksProvider({ children }: { children: ReactNode }) {
    const mission = useMission().mission
    const missionId = mission?.id
    const session = mission?.session
    const [read, setRead] = useState<Read | null>(null)

    useEffect(() => {
        if (!missionId || session === undefined) return
        let overtaken = false  // something else was opened before this answer arrived
        loadTracks().then((tracks) => {
            if (!overtaken) setRead({ missionId, session, tracks })
        }).catch((error) => sendError('mission', error))
        return () => { overtaken = true }
    }, [missionId, session])

    // What was read for an earlier mission or session is not this one's tracks.
    const tracks = read && read.missionId === missionId && read.session === session ? read.tracks : NONE
    return <TracksContext value={tracks}>{children}</TracksContext>
}

const NONE: Track[] = []

export default TracksProvider
