import { IconChevronDown, IconChevronRight, IconMinus, IconPlus } from '@tabler/icons-react'
import { useEffect, useRef, useState } from 'react'
import { sendError } from '../diagnostics/errorLog.ts'
import { BOX } from '../frame/Legend.tsx'
import { useMission, type OpenMission } from '../mission/mission.ts'
import { formatTime } from '../mission/missionTime.ts'
import { radioLabel } from '../people/peopleWords.ts'
import { useSectors } from '../sectors/sectors.ts'
import { loadLog, type LogLine, type Receipt } from './log.ts'
import { acknowledged, FILTERS, lineWords, opens, receipt, shownBy, typeLabel, typeOf, who, words } from './logWords.ts'

const TITLE = 'font-mono text-label tracking-widest uppercase'

type Props = {
    besidePanel?: boolean   // a panel is open, so the log starts to the right of it
}

// The Communication Log, at the bottom left of the map. It is folded to a small button
// until it is pressed. Open, it is a box that keeps clear of the map controls in the other
// corner, so it narrows when a panel opens beside it. Like those controls, it is raised to
// sit above the map's credits line.
function CommunicationLog({ besidePanel = false }: Props) {
    const { mission } = useMission()
    const [open, setOpen] = useState(false)
    const left = besidePanel ? 'left-[calc(var(--spacing-panel)+0.875rem)]' : 'left-3.5'

    return (
        <div className={`pointer-events-none absolute right-64 bottom-11 z-10 flex ${left}`}>
            {mission && open ? <OpenLog mission={mission} onFold={() => setOpen(false)} /> : (
                <button
                    type="button"
                    aria-label="Open the Communication Log"
                    aria-disabled={!mission}
                    title={mission ? 'Open the Communication Log' : 'Open a mission first'}
                    onClick={mission ? () => setOpen(true) : undefined}
                    className={`flex h-control items-center gap-3 rounded-box pr-2 pl-2.5 ${TITLE} ${BOX} ${mission ? 'cursor-pointer hover:bg-strip' : 'opacity-40'}`}
                >
                    Communication Log
                    <IconPlus size={12} stroke={2} aria-hidden />
                </button>
            )}
        </div>
    )
}

// What was read: the lines, or none when the reading failed, and the mission they were read for.
type Read = { missionId: string, lines: LogLine[] | null }

// The open mission's log lines; "reading" until they arrive, and "failed" when they could
// not be read. They are read when the log opens, again when the mission's session or
// status changes, and again when the sectors change: a sector given to a group, released
// or completed is a new line.
function useLines(mission: OpenMission): LogLine[] | 'reading' | 'failed' {
    const { sectors } = useSectors()
    const missionId = mission.id
    const readFor = `${mission.id} ${mission.session} ${mission.status}`
    const [read, setRead] = useState<Read | null>(null)

    useEffect(() => {
        let overtaken = false  // something else was asked for before this answer arrived
        loadLog().then((lines) => {
            if (!overtaken) setRead({ missionId, lines })
        }).catch((error) => {
            sendError('mission', error)
            if (!overtaken) setRead({ missionId, lines: null })
        })
        return () => { overtaken = true }
    }, [missionId, readFor, sectors])

    // What was read for another mission is not this mission's log.
    if (read?.missionId !== missionId) return 'reading'
    return read.lines ?? 'failed'
}

const CHIP = 'h-5 flex-none cursor-pointer rounded-full border px-2 font-mono text-label'

// The open log: the title strip with the type filters, the lines, and the send box.
function OpenLog({ mission, onFold }: { mission: OpenMission, onFold: () => void }) {
    const lines = useLines(mission)
    const [filter, setFilter] = useState('all')
    const [opened, setOpened] = useState<number | null>(null)  // the message whose radios are listed
    const list = useRef<HTMLUListElement>(null)
    const shown = typeof lines === 'string' ? [] : shownBy(lines, filter)

    // The newest line is the last, so the list is kept scrolled to its end.
    useEffect(() => {
        if (list.current) list.current.scrollTop = list.current.scrollHeight
    }, [lines, filter])

    function note(): string | null {
        if (lines === 'reading') return null
        if (lines === 'failed') return 'The log could not be read.'
        if (lines.length === 0) return 'Nothing logged yet.'
        return shown.length === 0 ? 'No lines of this type.' : null
    }
    const said = note()

    return (
        <section aria-label="Communication Log" className={`flex w-full max-w-[720px] flex-col overflow-hidden rounded-box ${BOX}`}>
            <div className="flex h-7.5 flex-none items-center gap-1.5 border-b border-ink bg-strip pr-1 pl-2.5">
                <h2 className={`flex-none pr-1.5 ${TITLE}`}>Communication Log</h2>
                {/* The chips that do not fit a narrow log are cut off, not wrapped. */}
                <div className="flex min-w-0 flex-1 gap-1.5 overflow-hidden">
                    {FILTERS.map(({ code, label }) => (
                        <button
                            key={code}
                            type="button"
                            aria-pressed={filter === code}
                            onClick={() => setFilter(code)}
                            className={`${CHIP} ${code === 'all' ? '' : 'lowercase'} ${filter === code ? 'border-ink bg-ink text-panel' : 'border-ink/35 hover:bg-panel'}`}
                        >
                            {label}
                        </button>
                    ))}
                </div>
                <button
                    type="button"
                    aria-label="Fold the Communication Log"
                    title="Fold the Communication Log"
                    onClick={onFold}
                    className="flex size-6 flex-none cursor-pointer items-center justify-center rounded-control hover:bg-panel"
                >
                    <IconMinus size={14} stroke={1.75} aria-hidden />
                </button>
            </div>
            {said ? <p className="px-2.5 py-2 font-medium text-muted">{said}</p> : (
                <ul ref={list} aria-label="Log lines" className="max-h-56 min-h-9 overflow-y-auto py-1">
                    {shown.map((line) => (
                        <Line
                            key={`${line.kind} ${line.kind === 'sector' ? line.event : ''} ${line.id}`}
                            line={line}
                            zone={mission.time_zone}
                            open={line.kind === 'message' && opened === line.id}
                            onPress={() => setOpened(opened === line.id ? null : line.id)}
                        />
                    ))}
                </ul>
            )}
            <SendBox />
        </section>
    )
}

const ROW = 'flex w-full items-baseline gap-2.5 px-2.5 py-1 text-left'

type LineProps = {
    line: LogLine
    zone: string            // the mission's time zone
    open: boolean           // its radios are listed under it
    onPress: () => void     // a line that opens was pressed
}

// One line: the time, who, the type tag, the words, and whether it was acknowledged. A send
// to several radios is a button that opens to list each radio and when it acknowledged.
function Line({ line, zone, open, onPress }: LineProps) {
    const type = typeOf(line)
    const from = who(line)
    const acked = acknowledged(line, zone)
    const Chevron = open ? IconChevronDown : IconChevronRight
    const parts = (
        <>
            <span className="w-15 flex-none tabular-nums text-muted">{formatTime(line.time, zone)}</span>
            {from && <span className="flex-none font-bold">{from}</span>}
            <span className={`flex-none rounded-full border border-ink px-2 font-mono text-label tracking-wider uppercase ${type === 'evidence' ? 'bg-ink text-panel' : ''}`}>
                {typeLabel(type)}
            </span>
            <span className="min-w-0 flex-1 font-medium">{words(line)}</span>
            {acked && <span className="flex-none font-mono text-label text-muted">{acked}</span>}
            {opens(line) && <Chevron size={12} stroke={2} aria-hidden className="flex-none self-center" />}
        </>
    )
    return (
        <li aria-label={lineWords(line, zone)}>
            {opens(line) ? (
                <button type="button" aria-expanded={open} onClick={onPress} className={`${ROW} cursor-pointer hover:bg-strip`}>{parts}</button>
            ) : <div className={ROW}>{parts}</div>}
            {open && line.kind === 'message' && <Radios radios={line.radios} zone={zone} />}
        </li>
    )
}

// Each radio of an opened line, and when it acknowledged. The newest line is at the bottom
// of the box, where there is no room under it, so the list is scrolled into view when it
// is first drawn.
function Radios({ radios, zone }: { radios: Receipt[], zone: string }) {
    const list = useRef<HTMLUListElement>(null)
    useEffect(() => {
        list.current?.scrollIntoView?.({ block: 'nearest' })  // a test's pretend browser has no scrollIntoView
    }, [])
    return (
        <ul ref={list} aria-label="Radios of this message" className="mx-2.5 mb-1 ml-20 flex flex-col gap-0.5 border-l-2 border-ink/20 py-0.5 pl-2.5">
            {radios.map((radio) => (
                <li key={radio.radio_id} className="flex items-baseline gap-2.5">
                    <span className="w-16 flex-none font-bold">{radioLabel(radio.radio_id)}</span>
                    <span className="font-mono text-label text-muted">{receipt(radio.ack_time, zone)}</span>
                </li>
            ))}
        </ul>
    )
}

const GREYED = 'Not available yet'

// The box for sending a message. The app does not send yet, so every part of it is greyed.
function SendBox() {
    return (
        <div className="flex h-9 flex-none border-t border-ink">
            <select disabled aria-label="Send to" title={GREYED} className="flex-none border-r border-ink px-2.5 font-bold opacity-40">
                <option>To</option>
            </select>
            <input
                disabled
                aria-label="Message to send"
                title={GREYED}
                placeholder="Instruction to send over the mesh"
                maxLength={200}
                className="min-w-0 flex-1 bg-field px-2.5 text-input font-medium opacity-40"
            />
            <span aria-hidden className="flex flex-none items-center bg-field pr-2.5 font-mono text-label text-muted opacity-40">0/200</span>
            <button type="button" aria-disabled title={GREYED} className="flex-none bg-ink px-4 text-input font-bold text-panel opacity-40">Send</button>
        </div>
    )
}

export default CommunicationLog
