import { useEffect, useState } from 'react'
import { createPortal } from 'react-dom'
import Button from '../frame/Button.tsx'
import Card from '../frame/Card.tsx'
import HintLine from '../frame/HintLine.tsx'
import { drawSector } from '../map/drawSector.ts'
import { polygonArea, type Position } from '../map/geo.ts'
import { useMissionMap } from '../map/missionMap.ts'
import { useSearchArea } from '../searchArea/searchArea.ts'
import { useSettings } from '../settings/settings.ts'
import { formatArea } from '../settings/units.ts'
import { useSectors } from './sectors.ts'
import { FULL } from './sectorWords.ts'

type Props = {
    id: number                      // the sector being edited
    hintSlot: HTMLElement | null    // the spot under the toolbar where the hint line goes
    onClose: () => void             // the editing is over: saved, or cancelled
}

const HINT = "Drag a corner to move it, or a side's middle to add a corner. Then press Done."

// Edit Shape, for a sector that has never been assigned, started from its card. The
// sector's corners can be dragged, and corners added at the middle of a side, with the same
// rules as when it was drawn. Done saves the new shape; Cancel or Escape leaves it as it was.
function EditSectorShape({ id, hintSlot, onClose }: Props) {
    const map = useMissionMap()
    const { area } = useSearchArea()
    const { sectors, changeShape } = useSectors()
    const { units } = useSettings().settings
    const sector = sectors.find((s) => s.id === id)
    const [corners, setCorners] = useState<Position[]>(sector?.corners ?? [])
    const [full, setFull] = useState(false)     // a corner added at a side's middle was refused
    const [busy, setBusy] = useState(false)     // the save is on its way
    const [failure, setFailure] = useState('')  // why the save did not work

    // The editing starts when this appears and stops when it goes. It starts from the shape
    // as saved, so it is read once, at the start.
    const [start] = useState(sector?.corners)
    useEffect(() => {
        if (!map || !area || !start) return
        const editing = drawSector(map, area, 'custom', {
            change(next) {
                setCorners(next)
                setFull(false)
            },
            full: () => setFull(true),
        })
        editing.edit(start)
        return () => editing.stop()
    }, [map, area, start])

    useEffect(() => {
        function onKeyDown(event: KeyboardEvent) {
            if (event.key === 'Escape') onClose()
        }
        window.addEventListener('keydown', onKeyDown)
        return () => window.removeEventListener('keydown', onKeyDown)
    }, [onClose])

    async function done() {
        setBusy(true)
        const reason = await changeShape(id, corners)
        setBusy(false)
        if (reason) setFailure(reason)
        else onClose()
    }

    if (!sector) return null
    const size = formatArea(polygonArea(corners), units)
    return (
        <>
            {/* A portal draws the hint line in another part of the page: its spot under the toolbar. */}
            {hintSlot && createPortal(<HintLine text={full ? FULL : HINT} figure={size} />, hintSlot)}
            <Card title={`Edit Sector ${sector.name}`}>
                <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1.5">
                    <dt className="font-medium text-muted">Points</dt>
                    <dd className="tabular-nums">{corners.length}</dd>
                    <dt className="font-medium text-muted">Area</dt>
                    <dd className="tabular-nums">{size}</dd>
                </dl>
                {/* role="alert" has a screen reader read the line out when it appears. */}
                {failure && <p role="alert" className="pt-2 font-medium text-red">{failure}</p>}
                <div className="flex gap-2 pt-3">
                    <Button look="dark" disabled={busy} onClick={done} className="flex-1">Done</Button>
                    <Button disabled={busy} onClick={onClose} className="flex-1">Cancel</Button>
                </div>
            </Card>
        </>
    )
}

export default EditSectorShape
