import { useEffect, useState, type ReactNode } from 'react'
import Button from '../frame/Button.tsx'
import ConfirmBox from '../frame/ConfirmBox.tsx'
import {
    changeTimeZone, closeMission, dayAndSession, endMission, endSession, reopenMission, resumeSession,
    startMission, startNextSession, STATUS_LABELS, useMission, type OpenMission,
} from './mission.ts'
import { FIELD } from './MissionList.tsx'
import MissionSummary from './MissionSummary.tsx'
import { formatDateTime, formatElapsed, TIME_ZONES, zoneLabel } from './missionTime.ts'

// The questions this view asks before it does something.
type Question = 'end-session' | 'end-mission' | 'next-session'

// What the Mission panel shows for the open mission: its facts, and the buttons its status
// allows. Every change goes to the backend first, and the facts change when it has saved.
function OpenMissionView({ mission }: { mission: OpenMission }) {
    const { run } = useMission()
    const [asking, setAsking] = useState<Question | null>(null)  // the question on screen, if any
    const [busy, setBusy] = useState(false)     // a request is on its way
    const [failure, setFailure] = useState('')  // why the last request did not work

    async function send(request: Promise<OpenMission | null>) {
        setAsking(null)
        setBusy(true)
        setFailure(await run(request))
        setBusy(false)
    }

    const { status, session, time_zone: zone } = mission
    const ended = status === 'ended'
    // A file whose zone is not one the form offers still shows in its own zone.
    const zones = TIME_ZONES.some((listed) => listed.name === zone) ? TIME_ZONES : [...TIME_ZONES, { name: zone, label: zone }]

    return (
        <div className="pt-1.5 pb-2.5">
            <h3 className="px-4 pt-3 pb-2 text-title font-bold">{mission.name}</h3>
            <dl className="grid grid-cols-[auto_1fr] items-center gap-x-3 gap-y-1.5 px-4">
                <Fact label="Status">{STATUS_LABELS[status]}</Fact>
                <Fact label="Session">{dayAndSession(mission)}</Fact>
                <Fact label="Time zone">
                    {ended ? zoneLabel(zone) : (
                        <select
                            aria-label="Time zone"
                            value={zone}
                            disabled={busy}
                            onChange={(event) => send(changeTimeZone(event.target.value))}
                            className={FIELD}
                        >
                            {zones.map((listed) => <option key={listed.name} value={listed.name}>{listed.label}</option>)}
                        </select>
                    )}
                </Fact>
                <Fact label="Started">{mission.start_time ? formatDateTime(mission.start_time, zone) : 'Not started'}</Fact>
                {mission.end_time && <Fact label="Ended">{formatDateTime(mission.end_time, zone)}</Fact>}
                {status === 'active' && mission.start_time && (
                    <Fact label="Elapsed"><span className="font-mono text-figure"><Elapsed since={mission.start_time} /></span></Fact>
                )}
            </dl>
            <MissionSummary />

            <div className="flex flex-col gap-2 px-4 pt-4">
                {status === 'planning' && (
                    <Button look="dark" disabled={busy} onClick={() => send(startMission())}>Start Mission</Button>
                )}
                {status === 'active' && (
                    <Button look="dark" disabled={busy} onClick={() => setAsking('end-session')}>End Session</Button>
                )}
                {status === 'paused' && <>
                    <Button look="dark" disabled={busy} onClick={() => setAsking('next-session')}>Start Session {session + 1}</Button>
                    <Button disabled={busy} onClick={() => send(resumeSession())}>Resume Session {session}</Button>
                </>}
                {(status === 'active' || status === 'paused') && (
                    <Button disabled={busy} onClick={() => setAsking('end-mission')}>End Mission</Button>
                )}
                {ended && <Button disabled={busy} onClick={() => send(reopenMission())}>Reopen</Button>}
            </div>
            {/* role="alert" has a screen reader read the line out when it appears. */}
            {failure && <p role="alert" className="px-4 pt-2 font-medium text-red">{failure}</p>}

            <div className="mt-4 flex flex-col border-t border-ink/20 px-4 pt-3">
                <Button disabled={busy} onClick={() => send(closeMission())}>Close Mission</Button>
            </div>

            {asking === 'end-session' && (
                <ConfirmBox
                    title={`End Session ${session}?`}
                    choices={[
                        { label: 'Cancel', onPress: () => setAsking(null) },
                        { label: 'End Session', main: true, onPress: () => send(endSession()) },
                    ]}
                >
                    The session is paused, and its teams and check-ins are closed at this time. It can be resumed afterward.
                </ConfirmBox>
            )}
            {asking === 'end-mission' && (
                <ConfirmBox
                    title="End the mission?"
                    choices={[
                        { label: 'Cancel', onPress: () => setAsking(null) },
                        { label: 'End Mission', main: true, onPress: () => send(endMission()) },
                    ]}
                >
                    The mission is over and nothing in it can be changed. Reopen undoes this.
                </ConfirmBox>
            )}
            {asking === 'next-session' && (
                <ConfirmBox
                    title={`Start Session ${session + 1}`}
                    stacked
                    choices={[
                        { label: 'Keep teams as they ended', main: true, onPress: () => send(startNextSession(true)) },
                        { label: 'Start with no teams', onPress: () => send(startNextSession(false)) },
                        { label: 'Cancel', onPress: () => setAsking(null) },
                    ]}
                >
                    The radios, people, search area, sectors and waypoints carry over. Nobody is checked in yet.
                </ConfirmBox>
            )}
        </div>
    )
}

// One line of the facts: a small label, and its value beside it.
function Fact({ label, children }: { label: string, children: ReactNode }) {
    return (
        <>
            <dt className="font-mono text-label tracking-widest text-muted uppercase">{label}</dt>
            <dd>{children}</dd>
        </>
    )
}

// The time since a moment, redrawn each second.
function Elapsed({ since }: { since: string }) {
    const [now, setNow] = useState(Date.now)
    useEffect(() => {
        const tick = setInterval(() => setNow(Date.now()), 1000)
        return () => clearInterval(tick)  // stops the ticking when the line leaves the screen
    }, [])
    return formatElapsed(now - Date.parse(since))
}

export default OpenMissionView
