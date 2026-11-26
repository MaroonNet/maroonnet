import { IconChevronDown, IconChevronRight } from '@tabler/icons-react'
import { useState } from 'react'
import Button from '../frame/Button.tsx'
import { HEADING } from '../mission/MissionList.tsx'
import { useMission } from '../mission/mission.ts'
import { usePeople } from '../people/people.ts'
import { groupLabel, radioLabel } from '../people/peopleWords.ts'
import GroupForm from './GroupForm.tsx'
import TeamForm from './TeamForm.tsx'
import type { Group, Radio } from './teams.ts'
import { groupColor, groupLine, lastPosition, teamsOf } from './teamWords.ts'

const NOTE = 'px-4 pt-3 font-medium text-muted'  // a line said in place of the list

// What the panel is showing: the list, the team form, the group form, or one group.
// radio and group are ids; none in a form means a new one.
type View =
    | { show: 'list' }
    | { show: 'team', radio: number | null }
    | { show: 'group-form', group: number | null, from: 'list' | 'group' }
    | { show: 'group', group: number }

type Props = {
    selected: number | null         // the radio of the selected team, whose card is up
    onPick: (id: number) => void    // a team was pressed
}

// What the Groups & Teams panel shows: each group with its teams, then the teams in no
// group. A team is a searcher radio with someone on it; the command post radio and relays
// are in the Mesh panel. Pressing a team selects it, which opens its card. Add Team and a
// team's Edit open the team form; Add Group and a group's Edit open the group form.
function TeamsPanel({ selected, onPick }: Props) {
    const { mission } = useMission()
    const { radios, groups } = usePeople()
    const [view, setView] = useState<View>({ show: 'list' })
    const list = () => setView({ show: 'list' })

    if (!mission) return <p className={NOTE}>No mission is open.</p>
    // Only a session in planning or active can be changed.
    const canChange = mission.status === 'planning' || mission.status === 'active'
    const teams = teamsOf(radios)
    const zone = mission.time_zone

    // The rows of some teams, each with its Edit button while the session can be changed.
    const rows = (label: string, shown: Radio[]) => (
        <ul aria-label={label}>
            {shown.map((radio) => (
                <TeamRow
                    key={radio.id}
                    radio={radio}
                    zone={zone}
                    selected={radio.id === selected}
                    onPick={() => onPick(radio.id)}
                    onEdit={canChange ? () => setView({ show: 'team', radio: radio.id }) : undefined}
                />
            ))}
        </ul>
    )
    const teamsIn = (group: Group) => teams.filter((radio) => radio.group_id === group.id)

    if (view.show === 'team') {
        const radio = radios.find((r) => r.id === view.radio) ?? null
        // key: another team starts the form afresh.
        return <TeamForm key={view.radio} radio={radio} onDone={list} />
    }
    if (view.show === 'group-form') {
        const group = groups.find((g) => g.id === view.group) ?? null
        const back = view.from === 'group' && group ? () => setView({ show: 'group', group: group.id }) : list
        return <GroupForm key={view.group} group={group} onDone={back} />
    }
    const viewed = view.show === 'group' ? groups.find((g) => g.id === view.group) : undefined
    if (viewed) {
        return (
            <div className="pb-3">
                <div className="px-4 pt-2">
                    <Button onClick={list} className="h-6.5 px-2">‹ Groups & Teams</Button>
                </div>
                <div className="flex items-center gap-2 px-4 pt-3">
                    <Swatch group={viewed.id} />
                    <h3 className="text-title font-bold">{groupLabel(viewed.id)}</h3>
                </div>
                <p className="px-4 pt-0.5 font-medium text-muted">{viewed.sector ? `Holds sector ${viewed.sector.name}` : 'Holds no sector'}</p>
                <h3 className={HEADING}>Teams · {teamsIn(viewed).length}</h3>
                {teamsIn(viewed).length === 0
                    ? <p className="px-4 font-medium text-muted">{canChange ? 'No teams. Edit the group to give it teams.' : 'No teams.'}</p>
                    : rows(groupLabel(viewed.id), teamsIn(viewed))}
                {canChange && (
                    <div className="px-4 pt-3">
                        <Button look="dark" onClick={() => setView({ show: 'group-form', group: viewed.id, from: 'group' })}>Edit Group</Button>
                    </div>
                )}
            </div>
        )
    }

    const ungrouped = teams.filter((radio) => radio.group_id === null)
    return (
        <div className="pb-3">
            {canChange && (
                <div className="flex gap-2 border-b border-ink/20 px-4 py-3">
                    <Button onClick={() => setView({ show: 'team', radio: null })}>Add Team</Button>
                    {/* A group is made from teams, so there must be one. */}
                    <Button
                        disabled={teams.length === 0}
                        title={teams.length === 0 ? 'Add a team first' : undefined}
                        onClick={() => setView({ show: 'group-form', group: null, from: 'list' })}
                    >
                        Add Group
                    </Button>
                </div>
            )}
            {teams.length === 0 && groups.length === 0 && (
                <>
                    <p className="px-4 pt-3">No teams yet.</p>
                    {canChange && <p className="px-4 pt-1 font-medium text-muted">Add Team puts checked-in people on a radio. Groups are made from teams.</p>}
                </>
            )}
            {groups.map((group) => (
                <section key={group.id} className="border-b border-ink/20 pb-1.5">
                    <button
                        type="button"
                        onClick={() => setView({ show: 'group', group: group.id })}
                        className="flex w-full cursor-pointer items-center gap-2 px-4 pt-2.5 pb-1 text-left font-bold hover:bg-strip"
                    >
                        <Swatch group={group.id} />
                        <span>{groupLine(group)}</span>
                    </button>
                    {teamsIn(group).length > 0 && rows(groupLabel(group.id), teamsIn(group))}
                </section>
            ))}
            {ungrouped.length > 0 && (
                <section>
                    <h3 className={HEADING}>No group</h3>
                    {rows('No group', ungrouped)}
                </section>
            )}
        </div>
    )
}

// The dot in a group's color.
function Swatch({ group }: { group: number }) {
    return <span aria-hidden className="size-2.5 flex-none rounded-full" style={{ background: groupColor(group) }} />
}

type RowProps = {
    radio: Radio
    zone: string
    selected: boolean
    onPick: () => void
    onEdit?: () => void     // left out: the session cannot be changed
}

// One team: its radio, how many searchers carry it, and the time of its newest position.
// Its arrow shows the searchers' names in place of the count, one per line. The arrow and
// Edit sit at the row's top right, so showing the names does not move them.
function TeamRow({ radio, zone, selected, onPick, onEdit }: RowProps) {
    const name = radioLabel(radio.id)
    const [open, setOpen] = useState(false)  // the names are shown
    const count = radio.people.length
    return (
        <li className={`relative ${selected ? 'bg-strip' : 'hover:bg-strip'}`}>
            <button
                type="button"
                aria-label={name}
                aria-current={selected ? true : undefined}
                onClick={onPick}
                className={`flex w-full cursor-pointer flex-col py-1.5 pl-4 text-left ${onEdit ? 'pr-24' : 'pr-12'}`}
            >
                <span className="text-input">{name}</span>
                {open
                    ? radio.people.map((person) => <span key={person.id} className="font-medium">{person.name}</span>)
                    : <span className="font-medium">{count} {count === 1 ? 'searcher' : 'searchers'}</span>}
                <span className="font-medium text-muted">{lastPosition(radio, zone)}</span>
            </button>
            <div className="absolute top-1.5 right-4 flex items-center gap-2">
                <button
                    type="button"
                    aria-label={`Names on ${name}`}
                    aria-expanded={open}
                    title={open ? 'Hide names' : 'Show names'}
                    onClick={() => setOpen(!open)}
                    className="flex size-6.5 cursor-pointer items-center justify-center rounded-control hover:bg-strip"
                >
                    {open ? <IconChevronDown size={14} stroke={1.75} aria-hidden /> : <IconChevronRight size={14} stroke={1.75} aria-hidden />}
                </button>
                {onEdit && <Button aria-label={`Edit ${name}`} onClick={onEdit} className="h-6.5 px-2">Edit</Button>}
            </div>
        </li>
    )
}

export default TeamsPanel
