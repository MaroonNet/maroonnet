import { useEffect, useState, type ReactNode } from 'react'
import { sendError } from '../diagnostics/errorLog.ts'
import { useMission } from '../mission/mission.ts'
import { loadOverlays, makeOverlay, ProbabilityContext, type MapRequest, type Overlay } from './probability.ts'

// The newest map as it was read, and the mission it was read for.
type Read = { missionId: string, newest: Overlay | null }

// Puts the probability board above the app. It asks the backend for the open mission's maps
// each time another mission is opened, and keeps the newest. A mission's maps are kept in
// its folder, not in a session's file, so a new session changes nothing here. It holds
// none while no mission is open.
function ProbabilityProvider({ children }: { children: ReactNode }) {
    const missionId = useMission().mission?.id
    const [read, setRead] = useState<Read | null>(null)

    useEffect(() => {
        if (!missionId) return
        let overtaken = false  // something else was opened before this answer arrived
        loadOverlays().then((overlays) => {
            if (!overtaken) setRead({ missionId, newest: overlays[0] ?? null })
        }).catch((error) => sendError('mission', error))
        return () => { overtaken = true }
    }, [missionId])

    // Has the model make a map, which takes some seconds. The backend answers with the new
    // map, which is then the newest.
    async function make(request: MapRequest): Promise<string> {
        if (!missionId) return 'No mission is open.'
        try {
            const made = await makeOverlay(request)
            setRead({ missionId, newest: made })
            return ''
        } catch (error) {
            return error instanceof Error ? error.message : String(error)
        }
    }

    // What was read for an earlier mission is not this mission's map.
    const newest = read && read.missionId === missionId ? read.newest : null
    return <ProbabilityContext value={{ newest, make }}>{children}</ProbabilityContext>
}

export default ProbabilityProvider
