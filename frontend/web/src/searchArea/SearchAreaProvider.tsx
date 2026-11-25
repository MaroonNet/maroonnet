import { useEffect, useState, type ReactNode } from 'react'
import { sendError } from '../diagnostics/errorLog.ts'
import { useMission } from '../mission/mission.ts'
import { loadSearchArea, saveSearchArea, SearchAreaContext, type SearchArea } from './searchArea.ts'

// A search area as it was read: the area, and the id of the mission it belongs to.
type Read = { missionId: string, area: SearchArea | null }

// Puts the search area board above the app. It asks the backend for the search area each
// time another mission is opened, and holds none while no mission is open.
function SearchAreaProvider({ children }: { children: ReactNode }) {
    const missionId = useMission().mission?.id
    const [read, setRead] = useState<Read | null>(null)

    useEffect(() => {
        if (!missionId) return
        let overtaken = false  // another mission was opened before this answer arrived
        loadSearchArea().then((area) => {
            if (!overtaken) setRead({ missionId, area })
        }).catch((error) => sendError('mission', error))
        return () => { overtaken = true }
    }, [missionId])

    async function save(area: SearchArea): Promise<string> {
        if (!missionId) return 'No mission is open.'
        try {
            setRead({ missionId, area: await saveSearchArea(area) })
            return ''
        } catch (error) {
            return error instanceof Error ? error.message : String(error)
        }
    }

    // What was read for an earlier mission is not this mission's search area.
    const current = read?.missionId === missionId ? read : null
    return (
        <SearchAreaContext value={{ area: current?.area ?? null, loadedFor: current?.missionId ?? null, save }}>
            {children}
        </SearchAreaContext>
    )
}

export default SearchAreaProvider
