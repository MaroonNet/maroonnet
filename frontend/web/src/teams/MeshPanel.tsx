import { IconChevronDown, IconChevronRight } from '@tabler/icons-react'
import { useState } from 'react'
import { HEADING } from '../mission/MissionList.tsx'
import { useMission } from '../mission/mission.ts'
import { formatTime } from '../mission/missionTime.ts'
import { usePeople } from '../people/people.ts'
import { groupLabel, radioLabel } from '../people/peopleWords.ts'
import type { Radio } from './teams.ts'
import { KIND_LABELS } from './teamWords.ts'

const NOTE = 'px-4 pt-3 font-medium text-muted'  // a line said in place of the lists
// The columns: the radio, its group or kind, the time of its last position, and its arrow.
const COLUMNS = 'grid grid-cols-[3.75rem_5.5rem_1fr_1.75rem] items-center gap-x-2'
const NO_POSITION = '–'

// What the Mesh panel shows: every radio of the open mission, in two sets: the searcher
// radios, then the command post radio and the relays. Each set is a table of the radio, its
// group (in the second set, its kind) and the time of its last position. A radio's arrow
// shows who carries it, one name per line, and its node number. It only lists: radio
// health (last heard, battery) comes with the radios themselves.
function MeshPanel() {
    const { mission } = useMission()
    const { radios } = usePeople()

    if (!mission) return <p className={NOTE}>No mission is open.</p>
    if (!radios.length) {
        return (
            <>
                <p className="px-4 pt-3">This mission has no radios.</p>
                <p className="px-4 pt-1 font-medium text-muted">A new mission starts with the radios listed in radios.json, in the app data folder.</p>
            </>
        )
    }
    const searchers = radios.filter((radio) => radio.kind === 'searcher')
    // The command post radio first, then the rest by number.
    const others = radios.filter((radio) => radio.kind !== 'searcher')
        .sort((a, b) => Number(b.kind === 'command_post') - Number(a.kind === 'command_post') || a.id - b.id)

    const set = (title: string, shown: Radio[], middle: 'Group' | 'Kind') => shown.length > 0 && (
        <section className="pb-1.5">
            <h3 className={HEADING}>{title} · {shown.length}</h3>
            <div className={`${COLUMNS} px-4 pb-1 font-mono text-label tracking-widest text-muted uppercase`}>
                <span>Radio</span><span>{middle}</span><span className="col-span-2">Last position</span>
            </div>
            <ul aria-label={title}>
                {shown.map((radio) => (
                    <RadioRow
                        key={radio.id}
                        radio={radio}
                        middle={middle === 'Group' ? groupLabel(radio.group_id) : KIND_LABELS[radio.kind]}
                        time={radio.last_position ? formatTime(radio.last_position.time, mission.time_zone) : NO_POSITION}
                    />
                ))}
            </ul>
        </section>
    )
    return (
        <div className="pb-3">
            {set('Searcher radios', searchers, 'Group')}
            {set('Command post and relays', others, 'Kind')}
        </div>
    )
}

type RowProps = {
    radio: Radio
    middle: string  // its group, or its kind
    time: string    // the time of its last position
}

// One radio's row. Under it, once its arrow is pressed, who carries it and its node number,
// labeled as a card labels its facts.
function RadioRow({ radio, middle, time }: RowProps) {
    const [open, setOpen] = useState(false)  // the details are shown
    const name = radioLabel(radio.id)
    return (
        <li>
            <div className={`${COLUMNS} px-4 py-0.5`}>
                <span className="text-input">{name}</span>
                <span className="truncate">{middle}</span>
                <span className="tabular-nums text-muted">{time}</span>
                <button
                    type="button"
                    aria-label={`Details of ${name}`}
                    aria-expanded={open}
                    title={open ? 'Hide details' : 'Show details'}
                    onClick={() => setOpen(!open)}
                    className="flex size-6.5 cursor-pointer items-center justify-center rounded-control hover:bg-strip"
                >
                    {open ? <IconChevronDown size={14} stroke={1.75} aria-hidden /> : <IconChevronRight size={14} stroke={1.75} aria-hidden />}
                </button>
            </div>
            {open && (
                <dl className="grid grid-cols-[4.5rem_1fr] items-baseline gap-x-3 gap-y-0.5 pr-4 pb-1.5 pl-7">
                    <dt className="font-medium text-muted">Carried by</dt>
                    <dd className="flex flex-col">
                        {radio.people.length === 0
                            ? <span className="font-medium text-muted">Nobody</span>
                            : radio.people.map((person) => <span key={person.id}>{person.name}</span>)}
                    </dd>
                    <dt className="font-medium text-muted">Node</dt>
                    <dd className="tabular-nums">{radio.node_num}</dd>
                </dl>
            )}
        </li>
    )
}

export default MeshPanel
