import { useId, useState } from 'react'
import Button from '../frame/Button.tsx'
import ConfirmBox from '../frame/ConfirmBox.tsx'
import { FIELD, HEADING } from '../mission/MissionList.tsx'
import { useMission } from '../mission/mission.ts'
import {
    addPlaceholder, addToRoster, changeRosterPerson, checkInFromRoster, deleteRosterPerson, usePeople,
    type PersonDetails, type RosterPerson,
} from './people.ts'
import { checkedInRosterIds, matches, personName, rosterName } from './peopleWords.ts'
import PersonForm from './PersonForm.tsx'

// What the dialog is showing: the two lists, the form for someone new, or one roster person.
type View = { show: 'lists' } | { show: 'add' } | { show: 'person', id: number, editing: boolean }

const TAG = 'font-mono text-label tracking-widest text-muted uppercase'

// The Manage Roster dialog, opened from the People panel. The roster is everyone the team
// knows, kept between missions. With a mission open it also lists who is checked in, and a
// roster person is checked in from here. Checking out is done on a person's own view.
function ManageRoster({ onClose }: { onClose: () => void }) {
    const titleId = useId()  // ties the title to the dialog, so a screen reader announces it
    const { mission } = useMission()
    const { roster, people, run } = usePeople()
    const [view, setView] = useState<View>({ show: 'lists' })
    const [search, setSearch] = useState('')
    const [busy, setBusy] = useState(false)     // a request is on its way
    const [failure, setFailure] = useState('')  // why the last request did not work

    // Only a session in planning or active takes a check-in.
    const canCheckIn = mission?.status === 'planning' || mission?.status === 'active'
    const checkedIn = people.filter((person) => person.checked_in)
    const placeholders = checkedIn.filter((person) => person.placeholder).length
    const inMission = checkedInRosterIds(roster, people)
    const shown = roster.filter((person) => matches(rosterName(person), search))
    const lists = () => setView({ show: 'lists' })

    async function send(request: Promise<unknown>) {
        setBusy(true)
        setFailure(await run(request))
        setBusy(false)
    }

    // Add Someone New: into the roster, and checked in when the mission can take it.
    async function addSomeone(details: PersonDetails): Promise<string> {
        const added = addToRoster(details)
        const reason = await run(canCheckIn ? added.then((person) => checkInFromRoster(person.id)) : added)
        if (!reason) lists()
        return reason
    }

    const selected = view.show === 'person' ? roster.find((person) => person.id === view.id) : undefined

    return (
        <div className="fixed inset-0 z-40 flex items-center justify-center bg-ink/40 p-4">
            <div
                role="dialog"
                aria-modal="true"
                aria-labelledby={titleId}
                className="flex h-170 max-h-full w-110 max-w-full flex-col overflow-hidden rounded-box border border-ink bg-panel shadow-[0_2px_10px_rgb(32_30_24/0.22)]"
            >
                <div className="flex h-9 flex-none items-center border-b border-ink bg-strip px-4">
                    <h2 id={titleId} className="font-mono text-label tracking-widest uppercase">Manage Roster</h2>
                </div>

                <div className="min-h-0 flex-1 overflow-auto pb-3">
                    {view.show === 'add' && (
                        <>
                            <h3 className={HEADING}>Add Someone New</h3>
                            <PersonForm
                                note={canCheckIn
                                    ? 'They are added to the roster and checked in to this mission.'
                                    : 'They are added to the roster for future missions.'}
                                submitLabel={canCheckIn ? 'Add and Check In' : 'Add to Roster'}
                                onSubmit={addSomeone}
                                onCancel={lists}
                            />
                        </>
                    )}

                    {view.show === 'person' && selected && (
                        <RosterPersonView
                            // key: another person, or leaving the form, starts the view afresh.
                            key={`${selected.id} ${view.editing}`}
                            person={selected}
                            status={inMission.has(selected.id)
                                ? `Checked in to ${mission?.name}.`
                                : `In the roster, not checked in to ${mission ? 'this mission' : 'a mission'}.`}
                            editing={view.editing}
                            onEdit={(editing) => setView({ show: 'person', id: selected.id, editing })}
                            onBack={lists}
                        />
                    )}

                    {(view.show === 'lists' || (view.show === 'person' && !selected)) && (
                        <>
                            <p className="px-4 pt-3 font-medium text-muted">
                                {mission
                                    ? `Check in everyone at the command post for ${mission.name}. People stay in the roster between missions.`
                                    : 'People stay in the roster between missions. Check them in once a mission is open.'}
                            </p>
                            {mission && (
                                <>
                                    <div className="flex items-end pr-4">
                                        <h3 className={`${HEADING} flex-1`}>Checked in · {checkedIn.length}</h3>
                                        {canCheckIn && (
                                            <Button disabled={busy} title="Hold a spot for someone not known yet" onClick={() => send(addPlaceholder())}>
                                                Add Placeholder
                                            </Button>
                                        )}
                                    </div>
                                    {checkedIn.length === 0 && (
                                        <p className="px-4 py-1 font-medium text-muted">
                                            No one yet. Check people in from the roster, or add a placeholder if you don't know who yet.
                                        </p>
                                    )}
                                    <ul aria-label="Checked in">
                                        {checkedIn.map((person) => (
                                            <li key={person.id} className="flex items-baseline gap-2 px-4 py-1">
                                                <span className="text-input">{personName(person)}</span>
                                                {person.placeholder && <span className={TAG}>Placeholder</span>}
                                            </li>
                                        ))}
                                    </ul>
                                </>
                            )}

                            <div className={`flex items-end pr-4 ${mission ? 'mt-3 border-t border-ink/20' : ''}`}>
                                <h3 className={`${HEADING} flex-1`}>Roster · {roster.length}</h3>
                                <Button disabled={busy} onClick={() => setView({ show: 'add' })}>Add Someone New</Button>
                            </div>
                            <div className="px-4 pt-2 pb-1">
                                <input
                                    value={search}
                                    onChange={(event) => setSearch(event.target.value)}
                                    placeholder="Search by name"
                                    aria-label="Search the roster by name"
                                    className={FIELD}
                                />
                            </div>
                            {/* role="alert" has a screen reader read the line out when it appears. */}
                            {failure && <p role="alert" className="px-4 py-1 font-medium text-red">{failure}</p>}
                            {roster.length === 0 && <p className="px-4 py-1 font-medium text-muted">The roster is empty. Add someone new.</p>}
                            {roster.length > 0 && shown.length === 0 && (
                                <p className="px-4 py-1 font-medium text-muted">No one in the roster matches "{search.trim()}".</p>
                            )}
                            <ul aria-label="Roster">
                                {shown.map((person) => (
                                    <li key={person.id} className="flex items-center gap-2 pr-4 hover:bg-strip">
                                        <button
                                            type="button"
                                            onClick={() => setView({ show: 'person', id: person.id, editing: false })}
                                            className="min-w-0 flex-1 cursor-pointer truncate py-1.5 pl-4 text-left text-input"
                                        >
                                            {rosterName(person)}
                                        </button>
                                        {inMission.has(person.id)
                                            ? <span className={TAG}>Checked in</span>
                                            : canCheckIn && (
                                                <Button
                                                    disabled={busy}
                                                    aria-label={`Check in ${rosterName(person)}`}
                                                    onClick={() => send(checkInFromRoster(person.id))}
                                                    className="h-6.5 px-2"
                                                >
                                                    + Check in
                                                </Button>
                                            )}
                                    </li>
                                ))}
                            </ul>
                        </>
                    )}
                </div>

                <div className="flex flex-none items-center border-t border-ink px-4 py-2.5">
                    <span className="flex-1 font-medium text-muted">
                        {mission
                            ? `${checkedIn.length - placeholders} checked in${placeholders ? ` · ${placeholders} placeholder${placeholders > 1 ? 's' : ''}` : ''}`
                            : `${roster.length} in the roster`}
                    </span>
                    <Button look="dark" onClick={onClose}>Done</Button>
                </div>
            </div>
        </div>
    )
}

type PersonProps = {
    person: RosterPerson
    status: string                          // a line saying whether they are checked in
    editing: boolean                        // the form is up in place of the facts
    onEdit: (editing: boolean) => void
    onBack: () => void                      // back to the lists, also after a delete
}

// One roster person in the dialog: their name and phone, with Edit and Delete.
function RosterPersonView({ person, status, editing, onEdit, onBack }: PersonProps) {
    const { run } = usePeople()
    const [asking, setAsking] = useState(false)  // the box asking before Delete is up
    const [busy, setBusy] = useState(false)
    const [failure, setFailure] = useState('')
    const name = rosterName(person)

    async function save(details: PersonDetails): Promise<string> {
        const reason = await run(changeRosterPerson(person.id, details))
        if (!reason) onEdit(false)
        return reason
    }

    async function deleteIt() {
        setAsking(false)
        setBusy(true)
        const reason = await run(deleteRosterPerson(person.id))
        if (reason) {
            setBusy(false)
            setFailure(reason)
        } else onBack()
    }

    if (editing) {
        return (
            <>
                <h3 className={HEADING}>Edit {name}</h3>
                <PersonForm start={person} submitLabel="Save" onSubmit={save} onCancel={() => onEdit(false)} />
            </>
        )
    }
    return (
        <div className="px-4 pt-2">
            <Button aria-label="Back" onClick={onBack} className="h-6.5 px-2">‹ Back</Button>
            <h3 className="pt-3 text-title font-bold">{name}</h3>
            <p className="pt-0.5 font-medium text-muted">{status}</p>
            <dl className="grid grid-cols-[auto_1fr] items-baseline gap-x-3 gap-y-1.5 pt-3">
                <dt className="font-medium text-muted">First name</dt><dd>{person.first_name}</dd>
                <dt className="font-medium text-muted">Middle initial</dt><dd>{person.middle_initial ?? 'None'}</dd>
                <dt className="font-medium text-muted">Last name</dt><dd>{person.last_name}</dd>
                <dt className="font-medium text-muted">Phone</dt><dd>{person.phone ?? 'Not on file'}</dd>
            </dl>
            {failure && <p role="alert" className="pt-2 font-medium text-red">{failure}</p>}
            <div className="flex gap-2 pt-3">
                <Button look="dark" disabled={busy} onClick={() => onEdit(true)}>Edit</Button>
                <Button disabled={busy} onClick={() => setAsking(true)}>Delete</Button>
            </div>
            {asking && (
                <ConfirmBox
                    title={`Delete ${name}?`}
                    choices={[
                        { label: 'Keep', onPress: () => setAsking(false) },
                        { label: 'Delete', onPress: deleteIt, main: true },
                    ]}
                >
                    They are removed from the roster. Missions they were in keep their records.
                </ConfirmBox>
            )}
        </div>
    )
}

export default ManageRoster
