import { IconChevronDown, IconChevronUp } from '@tabler/icons-react'
import { useState } from 'react'
import Button from '../frame/Button.tsx'
import ConfirmBox from '../frame/ConfirmBox.tsx'
import { FIELD, HEADING } from '../mission/MissionList.tsx'
import { useMission } from '../mission/mission.ts'
import { formatTime } from '../mission/missionTime.ts'
import { groupMapName, mapName } from '../teams/teamWords.ts'
import ManageRoster from './ManageRoster.tsx'
import { checkIn, saveToRoster, usePeople, type Person } from './people.ts'
import { matches, personName, sortPeople, type PeopleSort } from './peopleWords.ts'
import PersonView from './PersonView.tsx'

const NOTE = 'px-4 pt-3 font-medium text-muted'  // a line said in place of a list

// The table's columns, each a way to sort it: what its header says, and what it sorts by.
const COLUMNS: { by: PeopleSort['by'], label: string, words: string }[] = [
    { by: 'first', label: 'First', words: 'first name' },
    { by: 'last', label: 'Last', words: 'last name' },
    { by: 'radio', label: 'Radio', words: 'radio' },
    { by: 'group', label: 'Group', words: 'group' },
]
const TABLE = 'grid grid-cols-[1fr_1.15fr_2.75rem_2.75rem] gap-x-2'  // the columns' widths
const NONE = '–'  // in the Radio or Group column: no radio, or no group

type Props = {
    sort: PeopleSort                    // how the table is sorted; the app keeps it while the panel is closed
    onSort: (sort: PeopleSort) => void  // a column header was pressed
}

// What the People panel shows: the people checked in to the open mission, as a table of
// first name, last name, radio and group. Pressing a column header sorts the table by that
// column, and pressing it again turns the order around. Then those who are in the mission
// and not checked in (carried from the last session, or checked out during this one), in
// the table's name order, each with a Check In button. Pressing a person opens their view.
// The Manage Roster button opens the dialog, which works with no mission open too.
function PeoplePanel({ sort, onSort }: Props) {
    const { mission } = useMission()
    const { people, run } = usePeople()
    const [rosterOpen, setRosterOpen] = useState(false)
    const [selected, setSelected] = useState<number | null>(null)  // the person whose view is up
    const [search, setSearch] = useState('')
    const [busy, setBusy] = useState(false)     // a request is on its way
    const [failure, setFailure] = useState('')  // why the last request did not work
    // The person just checked in who is not in the roster: the box asks about saving them.
    const [offer, setOffer] = useState<Person | null>(null)

    // Only a session in planning or active can be changed.
    const canChange = mission?.status === 'planning' || mission?.status === 'active'
    const shown = people.filter((person) => matches(personName(person), search))
    const present = sortPeople(shown.filter((person) => person.checked_in), sort)
    // Someone not checked in carries nothing, so this list follows only the table's name order.
    const away = sortPeople(shown.filter((person) => !person.checked_in), { by: sort.by === 'first' ? 'first' : 'last', reversed: false })
    const viewed = people.find((person) => person.id === selected)

    async function checkInPerson(person: Person) {
        setBusy(true)
        const reason = await run(checkIn(person.id))
        setBusy(false)
        setFailure(reason)
        if (!reason && !person.in_roster && !person.placeholder) setOffer(person)
    }

    async function saveOffered() {
        const person = offer!
        setOffer(null)
        setFailure(await run(saveToRoster(person.id)))
    }

    if (mission && viewed) {
        // key: another person starts the view afresh.
        return <PersonView key={viewed.id} person={viewed} canChange={canChange} onBack={() => setSelected(null)} />
    }
    return (
        <div className="pb-3">
            <div className="border-b border-ink/20 px-4 py-3">
                <Button onClick={() => setRosterOpen(true)}>Manage Roster</Button>
            </div>
            {!mission && <p className={NOTE}>No mission is open. Manage Roster edits the roster; people are checked in once a mission is open.</p>}
            {mission && people.length === 0 && <p className={NOTE}>No one is checked in yet. Use Manage Roster to check people in.</p>}
            {mission && people.length > 0 && (
                <>
                    <div className="px-4 pt-3">
                        <input
                            value={search}
                            onChange={(event) => setSearch(event.target.value)}
                            placeholder="Search by name"
                            aria-label="Search people by name"
                            className={FIELD}
                        />
                    </div>
                    {/* role="alert" has a screen reader read the line out when it appears. */}
                    {failure && <p role="alert" className="px-4 pt-2 font-medium text-red">{failure}</p>}
                    {shown.length === 0 && <p className={NOTE}>No one matches "{search.trim()}".</p>}

                    {present.length > 0 && (
                        <>
                            <h3 className={HEADING}>Checked in · {present.length}</h3>
                            <div className={`${TABLE} px-4 pb-1`}>
                                {COLUMNS.map(({ by, label, words }) => {
                                    const active = sort.by === by
                                    return (
                                        <button
                                            key={by}
                                            type="button"
                                            aria-label={`Sort by ${words}`}
                                            aria-pressed={active}
                                            title={active ? 'Reverse the order' : `Sort by ${words}`}
                                            onClick={() => onSort({ by, reversed: active ? !sort.reversed : false })}
                                            className={`flex cursor-pointer items-center gap-0.5 text-left font-mono text-label tracking-widest uppercase ${active ? 'text-ink' : 'text-muted'}`}
                                        >
                                            {label}
                                            {active && (sort.reversed
                                                ? <IconChevronDown size={11} stroke={2} aria-hidden />
                                                : <IconChevronUp size={11} stroke={2} aria-hidden />)}
                                        </button>
                                    )
                                })}
                            </div>
                            <ul aria-label="Checked in">
                                {present.map((person) => (
                                    <li key={person.id}>
                                        <button
                                            type="button"
                                            aria-label={personName(person)}
                                            onClick={() => setSelected(person.id)}
                                            className={`${TABLE} w-full cursor-pointer items-baseline px-4 py-1.5 text-left hover:bg-strip`}
                                        >
                                            <span className="truncate text-input">{person.first_name}</span>
                                            <span className="truncate text-input">{person.last_name}</span>
                                            <span className="font-medium text-muted">{person.team_id === null ? NONE : mapName(person.team_id)}</span>
                                            <span className="font-medium text-muted">{person.group_id === null ? NONE : groupMapName(person.group_id)}</span>
                                        </button>
                                    </li>
                                ))}
                            </ul>
                        </>
                    )}

                    {away.length > 0 && (
                        <>
                            <h3 className={`${HEADING} ${present.length ? 'mt-2 border-t border-ink/20' : ''}`}>Not checked in · {away.length}</h3>
                            <ul aria-label="Not checked in">
                                {away.map((person) => (
                                    <li key={person.id} className="flex items-center gap-2 pr-4 hover:bg-strip">
                                        <button
                                            type="button"
                                            aria-label={personName(person)}
                                            onClick={() => setSelected(person.id)}
                                            className="flex min-w-0 flex-1 cursor-pointer flex-col py-1.5 pl-4 text-left"
                                        >
                                            <span className="truncate text-input">{personName(person)}</span>
                                            <span className="font-medium text-muted">
                                                {person.out_time ? `Checked out ${formatTime(person.out_time, mission.time_zone)}` : 'Not yet this session'}
                                            </span>
                                        </button>
                                        {canChange && (
                                            <Button
                                                disabled={busy}
                                                aria-label={`Check in ${personName(person)}`}
                                                onClick={() => checkInPerson(person)}
                                                className="h-6.5 px-2"
                                            >
                                                Check In
                                            </Button>
                                        )}
                                    </li>
                                ))}
                            </ul>
                        </>
                    )}
                </>
            )}

            {offer && (
                <ConfirmBox
                    title={`Save ${personName(offer)} to the roster?`}
                    choices={[
                        { label: 'Not now', onPress: () => setOffer(null) },
                        { label: 'Save to Roster', onPress: saveOffered, main: true },
                    ]}
                >
                    They are checked in, and are not in the roster. Saving keeps their name for later missions.
                </ConfirmBox>
            )}
            {rosterOpen && <ManageRoster onClose={() => setRosterOpen(false)} />}
        </div>
    )
}

export default PeoplePanel
