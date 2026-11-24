import { useEffect, useState, type FormEvent } from 'react'
import { sendError } from '../diagnostics/errorLog.ts'
import Button from '../frame/Button.tsx'
import { createMission, listMissions, openMission, STATUS_LABELS, useMission, type Mission } from './mission.ts'
import { laptopZone, TIME_ZONES } from './missionTime.ts'

export const HEADING = 'px-4 pt-3 pb-1 font-mono text-label tracking-widest text-muted uppercase'
export const FIELD = 'h-control w-full rounded-control border border-ink bg-field px-2 text-input font-medium'

// What the Mission panel shows with no mission open: every mission in the missions folder,
// each opened by pressing it, and the form that creates a new one.
function MissionList() {
    const { loadFailed, run } = useMission()
    const [missions, setMissions] = useState<Mission[] | null>(null)  // null: still on their way
    const [listFailed, setListFailed] = useState(false)
    const [name, setName] = useState('')
    const [zone, setZone] = useState(laptopZone)  // the form starts on the laptop's zone
    const [busy, setBusy] = useState(false)       // a request is on its way
    const [failure, setFailure] = useState('')    // why the last request did not work

    useEffect(() => {
        listMissions().then(setMissions).catch((error) => {
            sendError('mission', error)
            setListFailed(true)
        })
    }, [])

    // When the request works the mission is open, and the panel shows it in place of this list.
    async function send(request: ReturnType<typeof openMission>) {
        setBusy(true)
        setFailure(await run(request))
        setBusy(false)
    }

    function create(event: FormEvent) {
        event.preventDefault()  // the browser would otherwise reload the page
        send(createMission(name, zone))
    }

    return (
        <div className="pt-1.5 pb-2.5">
            {loadFailed && (
                <p className="px-4 pt-3 font-medium text-muted">The open mission could not be read from the backend.</p>
            )}
            <h3 className={HEADING}>Missions</h3>
            {listFailed && <p className="px-4 py-1 font-medium text-muted">The missions could not be listed.</p>}
            {missions?.length === 0 && <p className="px-4 py-1 font-medium text-muted">No missions yet.</p>}
            {missions?.map((mission) => (
                <button
                    key={mission.id}
                    type="button"
                    disabled={busy}
                    aria-label={`${mission.name} · ${STATUS_LABELS[mission.status]}`}
                    onClick={() => send(openMission(mission.id))}
                    className="flex w-full cursor-pointer items-baseline py-1.5 pr-4 pl-4 text-left hover:bg-strip"
                >
                    <span className="min-w-0 flex-1 truncate text-input">{mission.name}</span>
                    <span className="flex-none pl-1 font-medium text-muted">· {STATUS_LABELS[mission.status]}</span>
                </button>
            ))}

            <h3 className={`${HEADING} mt-2 border-t border-ink/20`}>New Mission</h3>
            <form onSubmit={create} className="flex flex-col gap-2 px-4 pt-1">
                <label className="flex flex-col gap-1 font-medium">
                    Name
                    <input value={name} onChange={(event) => setName(event.target.value)} maxLength={60} className={FIELD} />
                </label>
                <label className="flex flex-col gap-1 font-medium">
                    Time zone
                    <select value={zone} onChange={(event) => setZone(event.target.value)} className={FIELD}>
                        {TIME_ZONES.map((listed) => <option key={listed.name} value={listed.name}>{listed.label}</option>)}
                    </select>
                </label>
                <Button type="submit" look="dark" wide disabled={busy || name.trim() === ''} className="mt-1">Create Mission</Button>
            </form>
            {/* role="alert" has a screen reader read the line out when it appears. */}
            {failure && <p role="alert" className="px-4 pt-2 font-medium text-red">{failure}</p>}
        </div>
    )
}

export default MissionList
