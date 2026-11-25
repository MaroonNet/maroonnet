import { useState } from 'react'
import Button from '../frame/Button.tsx'
import ConfirmBox from '../frame/ConfirmBox.tsx'
import { FIELD, HEADING } from '../mission/MissionList.tsx'
import { usePeople } from '../people/people.ts'
import { groupLabel, inOrder, personName, radioLabel } from '../people/peopleWords.ts'
import { changeTeam, makeTeam, type Radio } from './teams.ts'
import { freePeople, freeRadios } from './teamWords.ts'

type Props = {
    radio: Radio | null     // the team being edited; none: a new team
    onDone: () => void      // saved or cancelled: back to the list
}

const NOTE = 'px-4 pt-1 font-medium text-muted'
const LABEL = 'block px-4 pt-3 pb-1 font-medium text-muted'

// The team form, in the Groups & Teams panel. A new team picks a radio that has nobody on
// it; an edited team keeps its radio. Either picks a group or none, and ticks its searchers
// from the checked-in people who carry no radio. This is the one place a team's people are
// changed.
function TeamForm({ radio, onDone }: Props) {
    const { people, radios, groups, run } = usePeople()
    const free = freeRadios(radios)
    const [radioId, setRadioId] = useState<number | null>(radio?.id ?? free[0]?.id ?? null)
    const [groupId, setGroupId] = useState<number | null>(radio?.group_id ?? null)
    const [ticked, setTicked] = useState<number[]>(radio?.people.map((person) => person.id) ?? [])
    const [asking, setAsking] = useState<'nobody' | 'group' | null>(null)  // the warning that is up
    const [busy, setBusy] = useState(false)     // the save is on its way
    const [failure, setFailure] = useState('')  // why the save did not work

    // Who can be ticked: the team's own people, then the people with no radio.
    const choices = [
        ...(radio?.people ?? []).map((person) => ({ id: person.id, name: person.name })),
        ...inOrder(freePeople(people)).map((person) => ({ id: person.id, name: personName(person) })),
    ]
    const was = radio?.group_id ?? null
    const wasGroup = groups.find((group) => group.id === was)
    const unchanged = radio !== null && groupId === was
        && ticked.length === radio.people.length && radio.people.every((person) => ticked.includes(person.id))

    function tick(id: number) {
        setTicked(ticked.includes(id) ? ticked.filter((other) => other !== id) : [...ticked, id])
    }

    // A change that leaves a radio with nobody, or a group with no teams, asks first.
    function pressSave() {
        if (radio && ticked.length === 0) setAsking('nobody')
        else if (radio && wasGroup && groupId !== was && wasGroup.radio_ids.length === 1) setAsking('group')
        else save()
    }

    async function save() {
        setAsking(null)
        setBusy(true)
        const ids = [...ticked].sort((a, b) => a - b)
        // A radio with nobody on it is in no group.
        const request = radio ? changeTeam(radio.id, ids, ids.length ? groupId : null) : makeTeam(radioId!, ids, groupId)
        const reason = await run(request)
        if (reason) {
            setBusy(false)
            setFailure(reason)
        } else onDone()
    }

    if (!radio && free.length === 0) {
        return (
            <div className="pb-3">
                <h3 className={HEADING}>New Team</h3>
                <p className="px-4">Every searcher radio already has someone on it.</p>
                <p className={NOTE}>Edit a team to change who carries its radio.</p>
                <div className="px-4 pt-3"><Button onClick={onDone}>Back</Button></div>
            </div>
        )
    }
    const name = radioLabel(radio?.id ?? radioId!)
    return (
        <div className="pb-3">
            <h3 className={HEADING}>{radio ? `Edit ${name}` : 'New Team'}</h3>
            {!radio && (
                <>
                    <label className={LABEL} htmlFor="team-radio">Radio</label>
                    <div className="px-4">
                        <select id="team-radio" value={radioId ?? ''} onChange={(event) => setRadioId(Number(event.target.value))} className={FIELD}>
                            {free.map((option) => <option key={option.id} value={option.id}>{radioLabel(option.id)}</option>)}
                        </select>
                    </div>
                    <p className={NOTE}>A team is one radio and the people carrying it.</p>
                </>
            )}

            <label className={LABEL} htmlFor="team-group">Group</label>
            <div className="px-4">
                <select
                    id="team-group"
                    value={groupId ?? ''}
                    onChange={(event) => setGroupId(event.target.value === '' ? null : Number(event.target.value))}
                    className={FIELD}
                >
                    <option value="">No group</option>
                    {groups.map((group) => <option key={group.id} value={group.id}>{groupLabel(group.id)}</option>)}
                </select>
            </div>

            <p className={LABEL}>Searchers · {ticked.length}</p>
            {choices.length === 0 && <p className="px-4 font-medium text-muted">No one is checked in without a radio. Check people in from the People panel.</p>}
            <ul aria-label="Searchers">
                {choices.map((choice) => (
                    <li key={choice.id}>
                        <label className="flex cursor-pointer items-center gap-2 px-4 py-1 hover:bg-strip">
                            <input
                                type="checkbox"
                                aria-label={choice.name}
                                checked={ticked.includes(choice.id)}
                                onChange={() => tick(choice.id)}
                                className="accent-ink"
                            />
                            <span className="text-input">{choice.name}</span>
                        </label>
                    </li>
                ))}
            </ul>
            <p className={NOTE}>Checked-in people with no radio are listed. To move someone from another team, take them off that team first.</p>

            {/* role="alert" has a screen reader read the line out when it appears. */}
            {failure && <p role="alert" className="px-4 pt-2 font-medium text-red">{failure}</p>}
            <div className="flex gap-2 px-4 pt-3">
                <Button look="dark" disabled={busy || (radio ? unchanged : ticked.length === 0)} onClick={pressSave}>Save Team</Button>
                <Button disabled={busy} onClick={onDone}>Cancel</Button>
            </div>

            {asking === 'nobody' && (
                <ConfirmBox
                    title={`Take everyone off ${name}?`}
                    choices={[
                        { label: 'Cancel', onPress: () => setAsking(null) },
                        { label: 'Take Everyone Off', onPress: save, main: true },
                    ]}
                >
                    {name} will have nobody on it{was === null ? '.' : `, and it leaves ${groupLabel(was)}.`}
                </ConfirmBox>
            )}
            {asking === 'group' && (
                <ConfirmBox
                    title={`Leave ${groupLabel(was)} with no teams?`}
                    choices={[
                        { label: 'Cancel', onPress: () => setAsking(null) },
                        { label: 'Move Team', onPress: save, main: true },
                    ]}
                >
                    {name} is the only team in {groupLabel(was)}. {groupLabel(was)} stays listed with no teams, and can be given teams again.
                </ConfirmBox>
            )}
        </div>
    )
}

export default TeamForm
