import { useState } from 'react'
import Button from '../frame/Button.tsx'
import { FIELD } from '../mission/MissionList.tsx'
import type { Waypoint } from '../waypoints/waypoints.ts'
import { loadModelStatus, MOST_HOURS, personLabel, pickModel, useProbability } from './probability.ts'

type Props = {
    waypoint: Waypoint      // the place the map is made from
    onMade: () => void      // a map was made, and is now the newest on the board
}

// The model a map is made with, and the kinds of person it can draw.
type Model = { name: string, kinds: string[] }

// Make Probability Map, on the card of a waypoint a search starts out from. The button
// opens a short form: the kind of person, from the kinds the model can draw, and the hours
// missing, which may be left empty. Make Map has the model draw the map, which takes a few
// seconds; if the model refuses, the form says why. A map is made here and nowhere else.
function MakeProbabilityMap({ waypoint, onMade }: Props) {
    const { make } = useProbability()
    const [open, setOpen] = useState(false)              // the form is on screen
    const [model, setModel] = useState<Model | null>(null)  // none until the backend has said what the model can draw
    const [problem, setProblem] = useState('')           // why the model cannot be used at all
    const [kind, setKind] = useState('')
    const [typedHours, setTypedHours] = useState('')
    const [busy, setBusy] = useState(false)              // the model is drawing
    const [failure, setFailure] = useState('')           // why this map was not made
    const [made, setMade] = useState(false)              // the last press made a map

    // Opens the form, and asks the backend whether the model can run and what it can draw.
    async function openForm() {
        setOpen(true)
        setMade(false)
        setFailure('')
        setProblem('')
        setModel(null)
        try {
            const status = await loadModelStatus()
            const picked = status.available ? pickModel(status) : null
            if (picked) {
                setModel(picked)
                setKind(picked.kinds[0])
            } else {
                setProblem(status.available ? 'no fitted model can draw a kind of person' : status.detail)
            }
        } catch (error) {
            setProblem(error instanceof Error ? error.message : String(error))
        }
    }

    // Empty: no hours. Otherwise a number the backend takes, or not a number it takes (NaN).
    const hours = typedHours.trim() === '' ? null : Number(typedHours)
    const hoursWrong = hours !== null && !(hours >= 0 && hours <= MOST_HOURS)

    async function makeMap(using: Model) {
        setBusy(true)
        setFailure('')
        const reason = await make({ lon: waypoint.lon, lat: waypoint.lat, model: using.name, category: kind, elapsed_h: hours })
        setBusy(false)
        if (reason) return setFailure(reason)
        setOpen(false)
        setMade(true)
        onMade()
    }

    return (
        <div className="mt-3 border-t border-ink/25 pt-3">
            {!open && <Button wide onClick={openForm}>Make Probability Map</Button>}
            {/* role="status" has a screen reader read the line out when it appears, without
                breaking in; role="alert" breaks in. */}
            {!open && made && <p role="status" className="pt-2 font-medium">Map made. It shows as the Probability heatmap layer.</p>}
            {open && !model && !problem && <p role="status" className="font-medium text-muted">Checking the model.</p>}
            {open && problem && (
                <>
                    <p role="alert" className="font-medium text-red">The model is not available: {problem}</p>
                    <Button wide onClick={() => setOpen(false)} className="mt-2.5">Close</Button>
                </>
            )}
            {open && model && (
                <>
                    <p className="font-mono text-label tracking-widest text-muted uppercase">Make Probability Map</p>
                    <div className="flex flex-col gap-2.5 pt-2">
                        <label className="flex flex-col gap-1 font-medium">
                            Kind of person
                            <select value={kind} disabled={busy} onChange={(event) => setKind(event.target.value)} className={FIELD}>
                                {model.kinds.map((listed) => <option key={listed} value={listed}>{personLabel(listed)}</option>)}
                            </select>
                        </label>
                        <label className="flex flex-col gap-1 font-medium">
                            Hours missing (optional)
                            <input
                                type="number"
                                min={0}
                                max={MOST_HOURS}
                                step="any"
                                value={typedHours}
                                disabled={busy}
                                onChange={(event) => setTypedHours(event.target.value)}
                                className={FIELD}
                            />
                        </label>
                    </div>
                    {hoursWrong && <p className="pt-2 font-medium text-red">Hours missing is a number from 0 to {MOST_HOURS}.</p>}
                    {busy && <p role="status" className="pt-2 font-medium text-muted">Making the map. This takes a few seconds.</p>}
                    {failure && <p role="alert" className="pt-2 font-medium text-red">{failure}</p>}
                    <div className="flex gap-2 pt-3">
                        <Button look="dark" disabled={busy || hoursWrong} onClick={() => makeMap(model)} className="flex-1">Make Map</Button>
                        <Button disabled={busy} onClick={() => setOpen(false)} className="flex-1">Cancel</Button>
                    </div>
                </>
            )}
        </div>
    )
}

export default MakeProbabilityMap
