import { useState } from 'react'
import Button from '../frame/Button.tsx'
import ConfirmBox from '../frame/ConfirmBox.tsx'
import { HEADING } from '../mission/MissionList.tsx'
import { usePeople } from '../people/people.ts'
import { groupLabel, radioLabel } from '../people/peopleWords.ts'
import { changeGroup, makeGroup, type Group } from './teams.ts'
import { carriedBy, teamsOf } from './teamWords.ts'

type Props = {
    group: Group | null     // the group being edited; none: a new group
    onDone: () => void      // saved or cancelled
}

// The group form, in the Groups & Teams panel: tick the teams that belong to the group.
// Every team is listed with the group it is in now; ticking one that is in another group
// moves it. A new group needs at least one team.
function GroupForm({ group, onDone }: Props) {
    const { radios, groups, run } = usePeople()
    const [ticked, setTicked] = useState<number[]>(group?.radio_ids ?? [])
    const [asking, setAsking] = useState(false)  // the warning is up
    const [busy, setBusy] = useState(false)      // the save is on its way
    const [failure, setFailure] = useState('')   // why the save did not work

    const unchanged = group !== null && ticked.length === group.radio_ids.length && group.radio_ids.every((id) => ticked.includes(id))
    // The groups this change would leave with no teams: another group whose every team was
    // ticked here, and this group when its last team was unticked.
    const emptied = groups.filter((other) => other.radio_ids.length > 0 && (other.id === group?.id
        ? ticked.length === 0
        : other.radio_ids.every((id) => ticked.includes(id))))
    const emptiedNames = emptied.map((other) => groupLabel(other.id)).join(' and ')

    function tick(id: number) {
        setTicked(ticked.includes(id) ? ticked.filter((other) => other !== id) : [...ticked, id])
    }

    async function save() {
        setAsking(false)
        setBusy(true)
        const ids = [...ticked].sort((a, b) => a - b)
        const reason = await run(group ? changeGroup(group.id, ids) : makeGroup(ids))
        if (reason) {
            setBusy(false)
            setFailure(reason)
        } else onDone()
    }

    return (
        <div className="pb-3">
            <h3 className={HEADING}>{group ? `Edit ${groupLabel(group.id)}` : 'New Group'}</h3>
            <p className="px-4 pb-1 font-medium text-muted">Tick the teams that belong to this group. A team in another group moves here.</p>
            <ul aria-label="Teams">
                {teamsOf(radios).map((radio) => (
                    <li key={radio.id}>
                        <label className="flex cursor-pointer items-baseline gap-2 px-4 py-1 hover:bg-strip">
                            <input
                                type="checkbox"
                                aria-label={radioLabel(radio.id)}
                                checked={ticked.includes(radio.id)}
                                onChange={() => tick(radio.id)}
                                className="flex-none translate-y-0.5 accent-ink"
                            />
                            <span className="min-w-0 flex-1">
                                <span className="block text-input">{radioLabel(radio.id)}</span>
                                <span className="block font-medium text-muted">{carriedBy(radio)}</span>
                            </span>
                            <span className="flex-none font-mono text-label tracking-widest text-muted uppercase">{groupLabel(radio.group_id)}</span>
                        </label>
                    </li>
                ))}
            </ul>

            {/* role="alert" has a screen reader read the line out when it appears. */}
            {failure && <p role="alert" className="px-4 pt-2 font-medium text-red">{failure}</p>}
            <div className="flex gap-2 px-4 pt-3">
                <Button
                    look="dark"
                    disabled={busy || (group ? unchanged : ticked.length === 0)}
                    onClick={() => emptied.length ? setAsking(true) : save()}
                >
                    Save Group
                </Button>
                <Button disabled={busy} onClick={onDone}>Cancel</Button>
            </div>

            {asking && (
                <ConfirmBox
                    title={`Leave ${emptiedNames} with no teams?`}
                    choices={[
                        { label: 'Cancel', onPress: () => setAsking(false) },
                        { label: 'Save Group', onPress: save, main: true },
                    ]}
                >
                    {emptiedNames} {emptied.length > 1 ? 'stay' : 'stays'} listed with no teams, and can be given teams again.
                </ConfirmBox>
            )}
        </div>
    )
}

export default GroupForm
