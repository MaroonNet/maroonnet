import { IconArrowBackUp, IconArrowForwardUp, type Icon } from '@tabler/icons-react'
import { useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import Button from '../frame/Button.tsx'
import Card from '../frame/Card.tsx'
import HintLine from '../frame/HintLine.tsx'
import { drawCustomShape, type CustomShapeDrawing, type DraftFacts } from '../map/drawCustomShape.ts'
import { drawSector, type SectorDrawing, type SectorShape } from '../map/drawSector.ts'
import { polygonArea, type Position } from '../map/geo.ts'
import { useMissionMap } from '../map/missionMap.ts'
import { MOST_CORNERS } from '../map/shapeDraft.ts'
import { useSearchArea } from '../searchArea/searchArea.ts'
import { useSettings } from '../settings/settings.ts'
import { formatArea } from '../settings/units.ts'
import { useSectors } from './sectors.ts'
import { FULL } from './sectorWords.ts'

type Props = {
    shape: SectorShape              // a rectangle, or a custom shape clicked out corner by corner
    hintSlot: HTMLElement | null    // the spot under the toolbar where the hint line goes
    toolSlot: HTMLElement | null    // the spot at the end of the toolbar, for Undo and Redo
    onDone: () => void              // the new sector was saved
}

const RECTANGLE_HINT = 'Drag on the map to draw a rectangle. Right-click the tool for a custom shape.'
const OUTSIDE = 'A sector must be inside the search area. Drag inside the dashed line.'
const EDIT_HINT = "Drag a corner to move it, or a side's middle to add a corner. Then Save the sector."
const NOTHING_CLICKED: DraftFacts = { count: 0, canUndo: false, canRedo: false, refused: null }

// The Draw Sector tool, drawn while it is the picked tool. The user drags a rectangle, or
// clicks a custom shape's corners, inside the search area; the New Sector card then shows
// its points and area, any corner can be dragged, and Save saves it. Discard or Escape takes
// it away. The toolbar offers the tool only once the mission has a search area.
function DrawSector({ shape, hintSlot, toolSlot, onDone }: Props) {
    const map = useMissionMap()
    const { area } = useSearchArea()
    const { add } = useSectors()
    const { units } = useSettings().settings
    const [corners, setCorners] = useState<Position[] | null>(null)  // the shape, while dragged and once drawn
    const [drawn, setDrawn] = useState(false)   // the shape is finished and on the card
    const [outside, setOutside] = useState(false)  // a rectangle was let go wholly outside the area
    const [full, setFull] = useState(false)        // a corner added at a side's middle was refused
    const [clicked, setClicked] = useState<DraftFacts>(NOTHING_CLICKED)  // a custom shape so far
    const [busy, setBusy] = useState(false)     // the save is on its way
    const [failure, setFailure] = useState('')  // why the save did not work
    // The drawings on the map. Refs keep them between redraws without causing one.
    const drawing = useRef<SectorDrawing | null>(null)
    const custom = useRef<CustomShapeDrawing | null>(null)

    // The drawing starts when the tool appears and stops when it goes. The search area is
    // the drawing's boundary; it cannot change while the tool is in use.
    useEffect(() => {
        if (!map || !area) return
        const started = drawSector(map, area, shape, {
            change(next) {
                setCorners(next)
                setOutside(false)  // a new drag has started
                setFull(false)
            },
            full: () => setFull(true),
            finish(next) {
                setCorners(next)
                setDrawn(true)
            },
            outside() {
                setCorners(null)
                setOutside(true)
            },
        })
        drawing.current = started
        // A custom shape's corners are clicked out first, then handed to the drawing above.
        const clicking = shape === 'custom' ? drawCustomShape(map, area, {
            draft: setClicked,
            finish(next) {
                started.edit(next)
                setCorners(next)
                setDrawn(true)
            },
        }) : null
        custom.current = clicking
        return () => {
            clicking?.stop()
            started.stop()
        }
    }, [map, area, shape])

    function discard() {
        drawing.current?.discard()
        custom.current?.discard()
        setCorners(null)
        setDrawn(false)
        setOutside(false)
        setClicked(NOTHING_CLICKED)
        setFailure('')
    }

    // Escape discards. While a custom shape is being clicked out, Enter closes it, Backspace
    // and Ctrl+Z (Cmd+Z on a Mac) undo, and Ctrl+Shift+Z redoes.
    const clicking = shape === 'custom' && !drawn
    useEffect(() => {
        function onKeyDown(event: KeyboardEvent) {
            if (event.key === 'Escape') discard()
            if (!clicking) return
            const command = event.ctrlKey || event.metaKey
            if (event.key === 'Enter') custom.current?.close()
            else if (event.key === 'Backspace' && !command) custom.current?.undo()
            else if (command && event.key.toLowerCase() === 'z') {
                event.preventDefault()  // not the browser's own undo
                if (event.shiftKey) custom.current?.redo()
                else custom.current?.undo()
            }
        }
        window.addEventListener('keydown', onKeyDown)
        return () => window.removeEventListener('keydown', onKeyDown)
    }, [clicking])

    async function save(next: Position[]) {
        setBusy(true)
        const reason = await add(next)
        setBusy(false)
        if (reason) setFailure(reason)
        else onDone()
    }

    const size = corners && formatArea(polygonArea(corners), units)
    const hint = drawn ? (full ? FULL : EDIT_HINT)
        : shape === 'custom' ? clickingHint(clicked)
        : outside ? OUTSIDE : RECTANGLE_HINT
    // While clicking a custom shape, the figure is the count of corners; otherwise its area.
    const figure = clicking ? (clicked.count ? `${clicked.count} of ${MOST_CORNERS}` : undefined) : size ?? undefined
    return (
        <>
            {/* Portals draw these in other parts of the page: the hint line under the
                toolbar, and Undo and Redo at its end. */}
            {hintSlot && createPortal(<HintLine text={hint} figure={figure} />, hintSlot)}
            {toolSlot && clicking && createPortal(
                <>
                    <span className="mx-1 h-5 w-px bg-strip" aria-hidden />
                    <SlotButton label="Undo" keys="Ctrl+Z" icon={IconArrowBackUp} enabled={clicked.canUndo} onPress={() => custom.current?.undo()} />
                    <SlotButton label="Redo" keys="Ctrl+Shift+Z" icon={IconArrowForwardUp} enabled={clicked.canRedo} onPress={() => custom.current?.redo()} />
                </>,
                toolSlot,
            )}
            {drawn && corners && (
                <Card title="New Sector">
                    <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1.5">
                        <dt className="font-medium text-muted">Points</dt>
                        <dd className="font-mono text-figure">{corners.length}</dd>
                        <dt className="font-medium text-muted">Area</dt>
                        <dd className="font-mono text-figure">{size}</dd>
                    </dl>
                    {/* role="alert" has a screen reader read the line out when it appears. */}
                    {failure && <p role="alert" className="pt-2 font-medium text-red">{failure}</p>}
                    <div className="flex gap-2 pt-3">
                        <Button look="dark" disabled={busy} onClick={() => save(corners)} className="flex-1">Save</Button>
                        <Button disabled={busy} onClick={discard} className="flex-1">Discard</Button>
                    </div>
                </Card>
            )}
        </>
    )
}

// What to do next while a custom shape is clicked out, or why the last click was refused.
function clickingHint({ count, refused }: DraftFacts): string {
    if (refused === 'full') return `A sector has at most ${MOST_CORNERS} corners. Close the shape, or remove a point.`
    if (refused === 'crosses') return 'Sides cannot cross.'
    if (refused === 'too-few') return 'A sector needs at least 3 corners.'
    if (count === 0) return 'Click the map to drop the first point.'
    if (count < 3) return 'Keep clicking to add points. Backspace removes the last one.'
    return 'Click the first point, double-click, or press Enter to close the sector.'
}

type SlotButtonProps = { label: string, keys: string, icon: Icon, enabled: boolean, onPress: () => void }

// Undo or Redo, in the toolbar's look. Greyed while there is nothing to undo or redo.
function SlotButton({ label, keys, icon: ButtonIcon, enabled, onPress }: SlotButtonProps) {
    return (
        <button
            type="button"
            aria-label={label}
            aria-keyshortcuts={keys}
            aria-disabled={enabled ? undefined : true}
            title={`${label} (${keys})`}
            onClick={enabled ? onPress : undefined}
            className={`flex h-control w-control items-center justify-center rounded-control ${enabled ? 'cursor-pointer hover:bg-strip' : 'opacity-40'}`}
        >
            <ButtonIcon size={18} stroke={1.75} aria-hidden />
        </button>
    )
}

export default DrawSector
