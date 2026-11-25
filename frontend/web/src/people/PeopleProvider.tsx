import { useEffect, useState, type ReactNode } from 'react'
import { sendError } from '../diagnostics/errorLog.ts'
import { useMission } from '../mission/mission.ts'
import { loadPeople, loadRoster, PeopleContext, type Person, type RosterPerson } from './people.ts'

// The people as they were read, and the mission they were read for.
type Read = { missionId: string, people: Person[] }

// Asks the backend for the roster and, with a mission open, its people.
function readBoth(missionOpen: boolean): Promise<[RosterPerson[], Person[]]> {
    return Promise.all([loadRoster(), missionOpen ? loadPeople() : []])
}

// Puts the people board above the app. The roster is read when the app opens, since it
// belongs to no mission. The mission's people are read each time another mission is
// opened, and again when its session or status changes: ending a session checks everyone
// out, and a new session starts with nobody checked in.
function PeopleProvider({ children }: { children: ReactNode }) {
    const mission = useMission().mission
    const missionId = mission?.id ?? null
    const readFor = mission ? `${mission.id} ${mission.session} ${mission.status}` : null
    const [roster, setRoster] = useState<RosterPerson[]>([])
    const [read, setRead] = useState<Read | null>(null)

    useEffect(() => {
        let overtaken = false  // something else was opened before this answer arrived
        readBoth(missionId !== null).then(([newRoster, people]) => {
            if (overtaken) return
            setRoster(newRoster)
            setRead(missionId ? { missionId, people } : null)
        }).catch((error) => sendError('mission', error))
        return () => { overtaken = true }
    }, [missionId, readFor])

    async function run(request: Promise<unknown>): Promise<string> {
        try {
            await request
            const [newRoster, people] = await readBoth(missionId !== null)
            setRoster(newRoster)
            setRead(missionId ? { missionId, people } : null)
            return ''
        } catch (error) {
            return error instanceof Error ? error.message : String(error)
        }
    }

    // What was read for an earlier mission is not this mission's people.
    const people = read?.missionId === missionId ? read.people : []
    return <PeopleContext value={{ roster, people, run }}>{children}</PeopleContext>
}

export default PeopleProvider
