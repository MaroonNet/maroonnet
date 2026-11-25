import { useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import Button from '../frame/Button.tsx'
import Card from '../frame/Card.tsx'
import HintLine from '../frame/HintLine.tsx'
import { drawRectangle, type RectangleDrawing } from '../map/drawRectangle.ts'
import { rectangleSize, type Bounds } from '../map/geo.ts'
import { useMissionMap } from '../map/missionMap.ts'
import { useSettings } from '../settings/settings.ts'
import { formatArea, formatDistance } from '../settings/units.ts'
import { useSearchArea } from './searchArea.ts'

type Props = {
    hintSlot: HTMLElement | null    // the spot under the toolbar where the hint line goes
    onDone: () => void              // the new search area was saved
}

// The Draw Search Area tool, drawn while it is the picked tool. The user drags a rectangle
// on the map; the New Search Area card then shows its size, and Apply saves it in place of
// the mission's current search area. Cancel or Escape takes the rectangle away.
function DrawSearchArea({ hintSlot, onDone }: Props) {
    const map = useMissionMap()
    const { save } = useSearchArea()
    const { units } = useSettings().settings
    const [dragged, setDragged] = useState<Bounds | null>(null)  // the rectangle while it is dragged
    const [drawn, setDrawn] = useState<Bounds | null>(null)      // the finished rectangle, on the card
    const [busy, setBusy] = useState(false)     // the save is on its way
    const [failure, setFailure] = useState('')  // why the save did not work
    // The drawing on the map. A ref keeps it between redraws without causing one.
    const drawing = useRef<RectangleDrawing | null>(null)

    // The drawing starts when the tool appears and stops when it goes.
    useEffect(() => {
        if (!map) return
        const started = drawRectangle(map, {
            drag(box) {
                setDrawn(null)
                setFailure('')
                setDragged(box)
            },
            finish(box) {
                setDragged(null)
                setDrawn(box)
            },
        })
        drawing.current = started
        return () => started.stop()
    }, [map])

    function cancel() {
        drawing.current?.clear()
        setDragged(null)
        setDrawn(null)
        setFailure('')
    }

    useEffect(() => {
        function onKeyDown(event: KeyboardEvent) {
            if (event.key === 'Escape') cancel()
        }
        window.addEventListener('keydown', onKeyDown)
        return () => window.removeEventListener('keydown', onKeyDown)
    }, [])

    async function apply(box: Bounds) {
        setBusy(true)
        const reason = await save(box)
        setBusy(false)
        if (reason) setFailure(reason)
        else onDone()
    }

    const shown = dragged ?? drawn
    const size = shown && rectangleSize(shown)
    const hint = drawn ? 'Apply to save the search area, or drag again to redraw it.' : 'Drag on the map to draw the search area.'
    return (
        <>
            {/* A portal draws the hint line in another part of the page: its spot under the toolbar. */}
            {hintSlot && createPortal(
                <HintLine text={hint} figure={size ? `${formatDistance(size.width, units)} × ${formatDistance(size.height, units)}` : undefined} />,
                hintSlot,
            )}
            {drawn && size && (
                <Card title="New Search Area">
                    <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1.5">
                        <dt className="font-medium text-muted">Width</dt>
                        <dd className="font-mono text-figure">{formatDistance(size.width, units)}</dd>
                        <dt className="font-medium text-muted">Height</dt>
                        <dd className="font-mono text-figure">{formatDistance(size.height, units)}</dd>
                        <dt className="font-medium text-muted">Area</dt>
                        <dd className="font-mono text-figure">{formatArea(size.area, units)}</dd>
                    </dl>
                    {/* role="alert" has a screen reader read the line out when it appears. */}
                    {failure && <p role="alert" className="pt-2 font-medium text-red">{failure}</p>}
                    <div className="flex gap-2 pt-3">
                        <Button look="dark" disabled={busy} onClick={() => apply(drawn)} className="flex-1">Apply</Button>
                        <Button disabled={busy} onClick={cancel} className="flex-1">Cancel</Button>
                    </div>
                </Card>
            )}
        </>
    )
}

export default DrawSearchArea
