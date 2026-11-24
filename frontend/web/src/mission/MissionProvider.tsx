import { useEffect, useState, type ReactNode } from 'react'
import { sendError } from '../diagnostics/errorLog.ts'
import { loadOpenMission, MissionContext, type OpenMission } from './mission.ts'

// Puts the mission board above the whole app. It asks the backend for the open mission
// once, when the page opens, and draws nothing until the answer arrives, so the screen
// never shows "no mission" for a moment and then a mission.
function MissionProvider({ children }: { children: ReactNode }) {
    const [mission, setMission] = useState<OpenMission | null>(null)
    const [loaded, setLoaded] = useState(false)
    const [loadFailed, setLoadFailed] = useState(false)

    // If the open mission cannot be read, the app carries on with none open.
    useEffect(() => {
        loadOpenMission().then(setMission).catch((error) => {
            sendError('mission', error)
            setLoadFailed(true)
        }).finally(() => setLoaded(true))
    }, [])

    async function run(request: Promise<OpenMission | null>): Promise<string> {
        try {
            setMission(await request)
            setLoadFailed(false)
            return ''
        } catch (error) {
            return error instanceof Error ? error.message : String(error)
        }
    }

    if (!loaded) return null
    return (
        <MissionContext value={{ mission, loadFailed, run }}>
            {children}
        </MissionContext>
    )
}

export default MissionProvider
