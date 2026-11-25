import { useEffect, useRef, useState, type ReactNode } from 'react'
import { createPortal } from 'react-dom'
import Button from '../frame/Button.tsx'
import Card from '../frame/Card.tsx'
import HintLine from '../frame/HintLine.tsx'
import { dropPin, type Pin } from '../map/dropPin.ts'
import type { Position } from '../map/geo.ts'
import { useMissionMap } from '../map/missionMap.ts'
import { formatPosition } from '../map/position.ts'
import { FIELD } from '../mission/MissionList.tsx'
import KindMarker from './KindMarker.tsx'
import { KINDS } from './kinds.ts'
import { bytes, DESCRIPTION_BYTES, NAME_BYTES, startingName } from './waypointWords.ts'
import { useWaypoints, type Waypoint } from './waypoints.ts'

type Props = {
    hintSlot: HTMLElement | null    // the spot under the toolbar where the hint line goes
    editing?: Waypoint              // given: this saved waypoint is being edited. Otherwise a new one is dropped
    // New: the waypoint was saved. Editing: it was saved, and this one took its place; or
    // the editing was canceled, and nothing is given.
    onDone: (saved?: Waypoint) => void
}

const DROP_HINT = 'Click the map to drop a waypoint.'
const MOVE_HINT = 'Drag the pin or click the map to move it. Then Save the waypoint.'
// A text box taller than one line.
const AREA = FIELD.replace('h-control', 'h-16 resize-none py-1.5')

// Places a waypoint: the Drop Waypoint tool, and the editing of a saved waypoint. A click
// on the map puts the pin there and opens the card, where the kind, the name, the
// description and the note are set; the pin can be dragged, or moved with another click.
// Save saves it. For a new waypoint, Discard or Escape takes the pin and the card away;
// for a saved one, Cancel or Escape ends the editing with nothing changed.
function PlaceWaypoint({ hintSlot, editing, onDone }: Props) {
    const map = useMissionMap()
    const { waypoints, add, change } = useWaypoints()
    const [position, setPosition] = useState<Position | null>(editing ? { lat: editing.lat, lon: editing.lon } : null)
    const [kind, setKind] = useState(editing?.kind ?? 'other')
    // What was typed in the Name box. None: nothing yet, so the box shows the kind's
    // starting name and follows the kind.
    const [typedName, setTypedName] = useState<string | null>(editing?.name ?? null)
    const [description, setDescription] = useState(editing?.description ?? '')
    const [note, setNote] = useState(editing?.note ?? '')
    const [busy, setBusy] = useState(false)     // the save is on its way
    const [failure, setFailure] = useState('')  // why the save did not work
    // The pin on the map. Its picture is drawn into pinElement from here; the ref keeps
    // the pin between redraws without causing one.
    const [pinElement] = useState(() => document.createElement('div'))
    const pin = useRef<Pin | null>(null)

    // The pin is on the map from when the tool appears until it goes. A waypoint being
    // edited starts with its pin where it is.
    const start = useRef(position)
    useEffect(() => {
        if (!map) return
        const placed = dropPin(map, pinElement, { move: setPosition }, start.current ?? undefined)
        pin.current = placed
        return () => placed.stop()
    }, [map, pinElement])

    function discard() {
        if (editing) return onDone()
        pin.current?.clear()
        setPosition(null)
        setKind('other')
        setTypedName(null)
        setDescription('')
        setNote('')
        setFailure('')
    }

    // Escape discards, or cancels the editing. The newest discard is kept in a ref, so the
    // listener is added once.
    const onEscape = useRef(discard)
    useEffect(() => { onEscape.current = discard })
    useEffect(() => {
        const onKeyDown = (event: KeyboardEvent) => { if (event.key === 'Escape') onEscape.current() }
        window.addEventListener('keydown', onKeyDown)
        return () => window.removeEventListener('keydown', onKeyDown)
    }, [])

    const name = typedName ?? startingName(kind, waypoints)
    const nameBytes = bytes(name.trim()), descriptionBytes = bytes(description.trim())
    const canSave = nameBytes > 0 && nameBytes <= NAME_BYTES && descriptionBytes <= DESCRIPTION_BYTES

    async function save(at: Position) {
        setBusy(true)
        const placing = { kind, lat: at.lat, lon: at.lon, name, description, note }
        const saved = await (editing ? change(editing.id, placing) : add(placing))
        setBusy(false)
        if (typeof saved === 'string') setFailure(saved)
        else onDone(editing ? saved : undefined)
    }

    return (
        <>
            {/* Portals draw these in other parts of the page: the hint line under the
                toolbar, and the pin's picture in the pin on the map. */}
            {hintSlot && createPortal(<HintLine text={position ? MOVE_HINT : DROP_HINT} />, hintSlot)}
            {createPortal(<KindMarker kind={kind} pin ringed />, pinElement)}
            {position && (
                <Card title={editing ? 'Edit Waypoint' : 'New Waypoint'}>
                    <p className="font-mono text-figure">{formatPosition(position)}</p>
                    <div className="flex flex-col gap-2.5 pt-2.5">
                        <Field label="Kind">
                            <select value={kind} onChange={(event) => setKind(event.target.value)} className={FIELD}>
                                {/* A kind the app does not know stays in the list while its waypoint is edited. */}
                                {!KINDS.some((listed) => listed.code === kind) && <option value={kind}>{kind}</option>}
                                {KINDS.map((listed) => <option key={listed.code} value={listed.code}>{listed.label}</option>)}
                            </select>
                        </Field>
                        <Field label="Name" count={[nameBytes, NAME_BYTES]}>
                            <input value={name} onChange={(event) => setTypedName(event.target.value)} className={FIELD} />
                        </Field>
                        <Field label="Description (sent to teams)" count={[descriptionBytes, DESCRIPTION_BYTES]}>
                            <textarea value={description} onChange={(event) => setDescription(event.target.value)} className={AREA} />
                        </Field>
                        <Field label="Note (command post only)">
                            <textarea value={note} onChange={(event) => setNote(event.target.value)} className={AREA} />
                        </Field>
                        {/* Sending is not built yet, so the list is greyed and does nothing. */}
                        <Field label="Send to">
                            <select disabled title="Not available yet" className={`${FIELD} opacity-40`}>
                                <option>Not available yet</option>
                            </select>
                        </Field>
                    </div>
                    {/* role="alert" has a screen reader read the line out when it appears. */}
                    {failure && <p role="alert" className="pt-2 font-medium text-red">{failure}</p>}
                    <div className="flex gap-2 pt-3">
                        <Button look="dark" disabled={busy || !canSave} onClick={() => save(position)} className="flex-1">Save</Button>
                        <Button disabled={busy} onClick={discard} className="flex-1">{editing ? 'Cancel' : 'Discard'}</Button>
                    </div>
                </Card>
            )}
        </>
    )
}

type FieldProps = {
    label: string
    count?: [number, number]    // the bytes used and the most allowed, shown beside the label
    children: ReactNode         // the box itself
}

// One box of the form under its label. A count past its limit turns red.
function Field({ label, count, children }: FieldProps) {
    return (
        <label className="flex flex-col gap-1 font-medium">
            <span className="flex items-baseline justify-between gap-2">
                {label}
                {/* aria-hidden: the count is not part of the box's name. */}
                {count && <span aria-hidden className={`font-mono text-label ${count[0] > count[1] ? 'text-red' : 'text-muted'}`}>{count[0]} / {count[1]}</span>}
            </span>
            {children}
        </label>
    )
}

export default PlaceWaypoint
