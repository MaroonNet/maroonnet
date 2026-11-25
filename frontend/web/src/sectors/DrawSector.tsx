import { useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import Button from '../frame/Button.tsx'
import Card from '../frame/Card.tsx'
import HintLine from '../frame/HintLine.tsx'
import { drawSector, type SectorDrawing } from '../map/drawSector.ts'
import { polygonArea, type Position } from '../map/geo.ts'
import { useMissionMap } from '../map/missionMap.ts'
import { useSearchArea } from '../searchArea/searchArea.ts'
import { useSettings } from '../settings/settings.ts'
import { formatArea } from '../settings/units.ts'
import { useSectors } from './sectors.ts'

type Props = {
    hintSlot: HTMLElement | null    // the spot under the toolbar where the hint line goes
    onDone: () => void              // the new sector was saved
}

const READY = 'Drag on the map to draw a sector.'
const OUTSIDE = 'A sector must be inside the search area. Drag inside the dashed line.'

// The Draw Sector tool, drawn while it is the picked tool. The user drags a rectangle inside
// the search area; the New Sector card then shows its points and area, any corner can be
// dragged, and Save saves it. Discard or Escape takes it away. The toolbar offers the tool
// only once the mission has a search area.
function DrawSector({ hintSlot, onDone }: Props) {
    const map = useMissionMap()
    const { area } = useSearchArea()
    const { add } = useSectors()
    const { units } = useSettings().settings
    const [shape, setShape] = useState<Position[] | null>(null)  // the corners, while drawn and once drawn
    const [drawn, setDrawn] = useState(false)   // the shape is finished and on the card
    const [hint, setHint] = useState(READY)
    const [busy, setBusy] = useState(false)     // the save is on its way
    const [failure, setFailure] = useState('')  // why the save did not work
    // The drawing on the map. A ref keeps it between redraws without causing one.
    const drawing = useRef<SectorDrawing | null>(null)

    // The drawing starts when the tool appears and stops when it goes. The search area is
    // the drawing's boundary; it cannot change while the tool is in use.
    useEffect(() => {
        if (!map || !area) return
        const started = drawSector(map, area, {
            change(corners) {
                setShape(corners)
                setHint((now) => now === OUTSIDE ? READY : now)  // a new drag has started
            },
            finish(corners) {
                setShape(corners)
                setDrawn(true)
                setHint('Drag a corner to move it, or Save the sector.')
            },
            outside() {
                setShape(null)
                setHint(OUTSIDE)
            },
        })
        drawing.current = started
        return () => started.stop()
    }, [map, area])

    function discard() {
        drawing.current?.discard()
        setShape(null)
        setDrawn(false)
        setHint(READY)
        setFailure('')
    }

    useEffect(() => {
        function onKeyDown(event: KeyboardEvent) {
            if (event.key === 'Escape') discard()
        }
        window.addEventListener('keydown', onKeyDown)
        return () => window.removeEventListener('keydown', onKeyDown)
    }, [])

    async function save(corners: Position[]) {
        setBusy(true)
        const reason = await add(corners)
        setBusy(false)
        if (reason) setFailure(reason)
        else onDone()
    }

    const size = shape && formatArea(polygonArea(shape), units)
    return (
        <>
            {/* A portal draws the hint line in another part of the page: its spot under the toolbar. */}
            {hintSlot && createPortal(<HintLine text={hint} figure={size ?? undefined} />, hintSlot)}
            {drawn && shape && (
                <Card title="New Sector">
                    <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1.5">
                        <dt className="font-medium text-muted">Points</dt>
                        <dd className="font-mono text-figure">{shape.length}</dd>
                        <dt className="font-medium text-muted">Area</dt>
                        <dd className="font-mono text-figure">{size}</dd>
                    </dl>
                    {/* role="alert" has a screen reader read the line out when it appears. */}
                    {failure && <p role="alert" className="pt-2 font-medium text-red">{failure}</p>}
                    <div className="flex gap-2 pt-3">
                        <Button look="dark" disabled={busy} onClick={() => save(shape)} className="flex-1">Save</Button>
                        <Button disabled={busy} onClick={discard} className="flex-1">Discard</Button>
                    </div>
                </Card>
            )}
        </>
    )
}

export default DrawSector
