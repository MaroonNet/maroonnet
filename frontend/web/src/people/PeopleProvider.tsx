import { useEffect, useState, type ReactNode } from 'react'
import { sendError } from '../diagnostics/errorLog.ts'
import { useMission } from '../mission/mission.ts'
import { loadGroups, loadRadios, type Group, type Radio } from '../teams/teams.ts'
import { loadPeople, loadRoster, PeopleContext, type Person, type RosterPerson } from './people.ts'

// What a mission's lists hold.
type Lists = { people: Person[], radios: Radio[], groups: Group[] }
const NOTHING: Lists = { people: [], radios: [], groups: [] }

// The lists as they were read, and the mission they were read for.
type Read = Lists & { missionId: string }

// Asks the backend for the roster and, with a mission open, its people, radios and groups.
async function readAll(missionOpen: boolean): Promise<[RosterPerson[], Lists]> {
    if (!missionOpen) return [await loadRoster(), NOTHING]
    const [roster, people, radios, groups] = await Promise.all([loadRoster(), loadPeople(), loadRadios(), loadGroups()])
    return [roster, { people, radios, groups }]
}

// Puts the people board above the app. The roster is read when the app opens, since it
// belongs to no mission. The mission's people, radios and groups are read each time another
// mission is opened, and again when its session or status changes: ending a session checks
// everyone out, and a new session starts with nobody checked in.
function PeopleProvider({ children }: { children: ReactNode }) {
    const mission = useMission().mission
    const missionId = mission?.id ?? null
    const readFor = mission ? `${mission.id} ${mission.session} ${mission.status}` : null
    const [roster, setRoster] = useState<RosterPerson[]>([])
    const [read, setRead] = useState<Read | null>(null)

    useEffect(() => {
        let overtaken = false  // something else was opened before this answer arrived
        readAll(missionId !== null).then(([newRoster, lists]) => {
            if (overtaken) return
            setRoster(newRoster)
            setRead(missionId ? { missionId, ...lists } : null)
        }).catch((error) => sendError('mission', error))
        return () => { overtaken = true }
    }, [missionId, readFor])

    async function run(request: Promise<unknown>): Promise<string> {
        try {
            await request
            const [newRoster, lists] = await readAll(missionId !== null)
            setRoster(newRoster)
            setRead(missionId ? { missionId, ...lists } : null)
            return ''
        } catch (error) {
            return error instanceof Error ? error.message : String(error)
        }
    }

    // What was read for an earlier mission is not this mission's.
    const { people, radios, groups } = read?.missionId === missionId ? read : NOTHING
    return <PeopleContext value={{ roster, people, radios, groups, run }}>{children}</PeopleContext>
}

export default PeopleProvider
