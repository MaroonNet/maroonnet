import { useId, useState } from 'react'
import Button from '../frame/Button.tsx'
import ConfirmBox from '../frame/ConfirmBox.tsx'
import { FIELD, HEADING } from '../mission/MissionList.tsx'
import { useMission } from '../mission/mission.ts'
import { formatTime } from '../mission/missionTime.ts'
import { checkOut, removePlaceholder, replacePlaceholder, saveToRoster, usePeople, type Person } from './people.ts'
import { checkedInRosterIds, groupLabel, historyLine, personName, radioLabel, rosterName } from './peopleWords.ts'

type Props = {
    person: Person
    canChange: boolean      // the session is in planning or active
    onBack: () => void      // back to the list, also after the person is removed
}

const LABEL = 'font-medium text-muted'

// One person of the open mission, in the People panel: their phone, what they carry, and
// their history. This is where a person is checked out, where someone who is not in the
// roster is saved to it, and where a placeholder is replaced or removed.
function PersonView({ person, canChange, onBack }: Props) {
    const carryingId = useId()
    const { mission } = useMission()
    const { roster, people, run } = usePeople()
    const [asking, setAsking] = useState<'check-out' | 'remove' | null>(null)  // the question that is up
    const [busy, setBusy] = useState(false)     // a request is on its way
    const [failure, setFailure] = useState('')  // why the last request did not work
    if (!mission) return null
    const zone = mission.time_zone
    const name = personName(person)

    // Answers whether it worked.
    async function send(request: Promise<unknown>): Promise<boolean> {
        setAsking(null)
        setBusy(true)
        const reason = await run(request)
        setBusy(false)
        setFailure(reason)
        return !reason
    }

    async function remove() {
        if (await send(removePlaceholder(person.id))) onBack()
    }

    // A placeholder takes the name of a roster person who is not checked in.
    const inMission = checkedInRosterIds(roster, people)
    const standIns = roster.filter((rosterPerson) => !inMission.has(rosterPerson.id))

    const cameIn = person.in_time && `Checked in ${formatTime(person.in_time, zone)}`
    const left = person.out_time && `Checked out ${formatTime(person.out_time, zone)}`
    // A session that has ended is read as it stood at its end, so it shows both times.
    const status = person.checked_in ? [cameIn, left].filter(Boolean).join(' · ') : left || 'Not checked in this session'

    return (
        <div className="pb-3">
            <div className="px-4 pt-2">
                <Button aria-label="Back to People" onClick={onBack} className="h-6.5 px-2">‹ People</Button>
            </div>
            <div className="flex items-baseline gap-2 px-4 pt-3">
                <h3 className="text-title font-bold">{name}</h3>
                {person.placeholder && <span className="font-mono text-label tracking-widest text-muted uppercase">Placeholder</span>}
            </div>
            <p className={`px-4 pt-0.5 ${LABEL}`}>{status}</p>

            {!person.placeholder && (
                <p className="px-4 pt-2">
                    {person.roster_id !== null
                        ? person.phone ?? <span className={LABEL}>No phone on file</span>
                        : <span className={LABEL}>{person.in_roster ? 'Two people in the roster have this name, so no phone is shown.' : 'Not in the roster.'}</span>}
                </p>
            )}
            {!person.placeholder && !person.in_roster && (
                <div className="px-4 pt-2">
                    <Button disabled={busy} onClick={() => send(saveToRoster(person.id))}>Save to Roster</Button>
                </div>
            )}

            <h3 id={carryingId} className={HEADING}>Carrying</h3>
            {person.team_id === null
                ? <p className={`px-4 ${LABEL}`}>No radio. Not on a team.</p>
                : (
                    <dl role="group" aria-labelledby={carryingId} className="grid grid-cols-[auto_1fr] items-baseline gap-x-3 gap-y-1 px-4">
                        <dt className={LABEL}>Radio</dt><dd>{radioLabel(person.team_id)}</dd>
                        <dt className={LABEL}>Group</dt><dd>{groupLabel(person.group_id)}</dd>
                        <dt className={LABEL}>Shared with</dt><dd>{person.shares.join(', ') || 'No one'}</dd>
                    </dl>
                )}

            {person.placeholder && (
                <div className="flex flex-col gap-2 px-4 pt-3">
                    <p className={LABEL}>Placeholder for a searcher who is not known yet. Replace it with a real person; they keep its team and radio.</p>
                    {canChange && (
                        <select
                            aria-label="Replace with"
                            value=""
                            disabled={busy}
                            onChange={(event) => send(replacePlaceholder(person.id, Number(event.target.value)))}
                            className={FIELD}
                        >
                            <option value="">Replace with…</option>
                            {standIns.map((rosterPerson) => <option key={rosterPerson.id} value={rosterPerson.id}>{rosterName(rosterPerson)}</option>)}
                        </select>
                    )}
                    {canChange && person.can_remove && <Button disabled={busy} onClick={() => setAsking('remove')}>Remove</Button>}
                </div>
            )}

            {canChange && person.checked_in && (
                <div className="flex flex-col px-4 pt-3">
                    <Button disabled={busy} onClick={() => person.last_on_radio ? setAsking('check-out') : send(checkOut(person.id))}>
                        Check Out of Mission
                    </Button>
                </div>
            )}
            {/* role="alert" has a screen reader read the line out when it appears. */}
            {failure && <p role="alert" className="px-4 pt-2 font-medium text-red">{failure}</p>}

            <h3 className={`${HEADING} mt-3 border-t border-ink/20`}>History</h3>
            {person.history.length === 0 && <p className={`px-4 ${LABEL}`}>No activity in this session.</p>}
            <ul aria-label="History">
                {person.history.map((event, index) => (
                    <li key={index} className="flex gap-3 px-4 py-0.5">
                        <span className="w-16 flex-none tabular-nums text-muted">{formatTime(event.time, zone)}</span>
                        <span>{historyLine(event)}</span>
                    </li>
                ))}
            </ul>

            {asking === 'check-out' && (
                <ConfirmBox
                    title={`Check out ${name}?`}
                    choices={[
                        { label: 'Cancel', onPress: () => setAsking(null) },
                        { label: 'Check Out', onPress: () => send(checkOut(person.id)), main: true },
                    ]}
                >
                    {name} is the only searcher on {radioLabel(person.team_id!)}. Checking out leaves the radio with nobody on it
                    {person.group_id === null ? '.' : `, and the radio leaves ${groupLabel(person.group_id)}.`}
                </ConfirmBox>
            )}
            {asking === 'remove' && (
                <ConfirmBox
                    title={`Remove ${name}?`}
                    choices={[
                        { label: 'Keep', onPress: () => setAsking(null) },
                        { label: 'Remove', onPress: remove, main: true },
                    ]}
                >
                    The placeholder is removed from the mission. This cannot be undone.
                </ConfirmBox>
            )}
        </div>
    )
}

export default PersonView
