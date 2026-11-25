import { useEffect, useState, type ReactNode } from 'react'
import { sendError } from '../diagnostics/errorLog.ts'
import type { Position } from '../map/geo.ts'
import { useMission } from '../mission/mission.ts'
import { addSector, changeSectorShape, deleteSector, loadSectors, SectorsContext, type Sector } from './sectors.ts'

// Sectors as they were read: the sectors, and what was open when they were read.
type Read = { readFor: string, missionId: string, sectors: Sector[] }

// Puts the sectors board above the app. It asks the backend for the sectors each time
// another mission is opened, and again when the open mission's session or status changes:
// ending a mission can turn a sector from searching to partial, and a new session's file
// holds its own copy. It holds none while no mission is open.
function SectorsProvider({ children }: { children: ReactNode }) {
    const mission = useMission().mission
    const missionId = mission?.id
    const readFor = mission ? `${mission.id} ${mission.session} ${mission.status}` : null
    const [read, setRead] = useState<Read | null>(null)

    useEffect(() => {
        if (!missionId || !readFor) return
        let overtaken = false  // something else was opened before this answer arrived
        loadSectors().then((sectors) => {
            if (!overtaken) setRead({ readFor, missionId, sectors })
        }).catch((error) => sendError('mission', error))
        return () => { overtaken = true }
    }, [missionId, readFor])

    // Sends one change to the backend. Once it is saved, change(sectors) gives the board's
    // new list from the one it had. The answer is empty when it worked, and the reason when
    // it did not.
    async function saveThen<Answer>(send: () => Promise<Answer>, change: (sectors: Sector[], answer: Answer) => Sector[]): Promise<string> {
        if (!missionId || !readFor) return 'No mission is open.'
        try {
            const answer = await send()
            setRead((now) => {
                const before = now?.missionId === missionId ? now.sectors : []
                return { readFor, missionId, sectors: change(before, answer) }
            })
            return ''
        } catch (error) {
            return error instanceof Error ? error.message : String(error)
        }
    }

    // Kept in number order: a new sector can take the number of one just deleted.
    const add = (corners: Position[]) => saveThen(() => addSector(corners),
        (sectors, added) => [...sectors, added].sort((a, b) => a.id - b.id))
    const changeShape = (id: number, corners: Position[]) => saveThen(() => changeSectorShape(id, corners),
        (sectors, changed) => sectors.map((sector) => sector.id === id ? changed : sector))
    const remove = (id: number) => saveThen(() => deleteSector(id),
        (sectors) => sectors.filter((sector) => sector.id !== id))

    // What was read for an earlier mission is not this mission's sectors. Sectors read
    // before the session or status changed are still this mission's, and are shown until
    // the new reading arrives.
    const current = read?.missionId === missionId ? read : null
    return (
        <SectorsContext value={{ sectors: current?.sectors ?? [], loadedFor: current?.missionId ?? null, add, changeShape, remove }}>
            {children}
        </SectorsContext>
    )
}

export default SectorsProvider
