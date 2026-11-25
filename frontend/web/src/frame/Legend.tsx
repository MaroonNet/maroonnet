import { IconList } from '@tabler/icons-react'
import { useState, type CSSProperties } from 'react'
import { SECTOR_COLORS } from '../sectors/looks.ts'
import { useSectors } from '../sectors/sectors.ts'
import { standingOf, STANDINGS, STATUS_LABELS, type Standing } from '../sectors/sectorWords.ts'
import KindMarker from '../waypoints/KindMarker.tsx'
import { KINDS } from '../waypoints/kinds.ts'
import { useWaypoints } from '../waypoints/waypoints.ts'

// A box floating over the map.
export const BOX = 'pointer-events-auto border border-ink bg-panel shadow-[0_2px_10px_rgb(32_30_24/0.22)]'

// A small picture of each sector look, drawn as the map draws it. A sector being searched
// is in its group's color, so its picture is a plain grey with a fill.
const stripes = `repeating-linear-gradient(135deg, ${SECTOR_COLORS.partial} 0 2px, transparent 2px 5px)`
const SWATCHES: Record<Standing, CSSProperties> = {
    drawn: { borderColor: SECTOR_COLORS.drawn },
    assigned: { borderColor: SECTOR_COLORS.assigned },
    searching: { borderColor: '#6b6a64', background: 'rgb(107 106 100 / 0.25)' },
    partial: { borderColor: SECTOR_COLORS.partial, background: stripes },
    completed: { borderColor: SECTOR_COLORS.completed, background: 'rgb(33 138 69 / 0.18)' },
}
// What tells two looks of one color apart, said beside the name.
const HOW: Partial<Record<Standing, string>> = { assigned: 'labeled with its group', searching: "in its group's color" }

const HEADING = 'font-mono text-label tracking-widest text-muted uppercase'

// The legend: a button that opens into a box in its place, and folds back to the button.
// It counts the open mission's sectors by status and its waypoints by kind, every status
// and kind listed, so it is also the key to the map's colors and icons. It is never taller
// than a third of the screen; past that its rows scroll.
function Legend() {
    const [open, setOpen] = useState(false)
    const { sectors } = useSectors()
    const { waypoints } = useWaypoints()

    if (!open) {
        return (
            <button
                type="button"
                aria-label="Show legend"
                title="Show legend"
                onClick={() => setOpen(true)}
                className={`flex size-11 cursor-pointer items-center justify-center rounded-control hover:bg-strip ${BOX}`}
            >
                <IconList size={20} stroke={1.75} aria-hidden />
            </button>
        )
    }
    const sectorCount = (standing: Standing) => sectors.filter((sector) => standingOf(sector) === standing).length
    const waypointCount = (kind: string) => waypoints.filter((waypoint) => waypoint.kind === kind).length
    return (
        <section aria-label="Legend" className={`flex max-h-[33vh] w-60 flex-col overflow-hidden rounded-box ${BOX}`}>
            <div className="flex h-7.5 flex-none items-center border-b border-ink bg-strip pr-1 pl-2.5">
                <h2 className="flex-1 font-mono text-label tracking-widest uppercase">Legend</h2>
                <button
                    type="button"
                    aria-label="Collapse legend"
                    title="Collapse legend"
                    onClick={() => setOpen(false)}
                    className="flex size-6 cursor-pointer items-center justify-center rounded-control hover:bg-panel"
                >
                    <IconList size={14} stroke={1.75} aria-hidden />
                </button>
            </div>
            {sectors.length === 0 && waypoints.length === 0 ? <p className="px-2.5 py-2 font-medium text-muted">Nothing to show yet.</p> : (
                <div className="min-h-0 flex-1 overflow-y-auto px-2.5 py-2">
                    <h3 className={HEADING}>Sectors</h3>
                    <ul aria-label="Sectors" className="flex flex-col gap-1.5 pt-1.5">
                        {STANDINGS.map((standing) => (
                            <li key={standing} className="flex items-center gap-2" title={HOW[standing]}>
                                <span aria-hidden className="h-3.5 w-5 flex-none border-2" style={SWATCHES[standing]} />
                                <span className="flex-1">{STATUS_LABELS[standing]}</span>
                                <span className="font-mono text-figure">{sectorCount(standing)}</span>
                            </li>
                        ))}
                    </ul>
                    <h3 className={`${HEADING} pt-3`}>Waypoints</h3>
                    <ul aria-label="Waypoints" className="flex flex-col gap-1.5 pt-1.5">
                        {KINDS.map((kind) => (
                            <li key={kind.code} className="flex items-center gap-2">
                                <KindMarker kind={kind.code} small />
                                <span className="flex-1">{kind.label}</span>
                                <span className="font-mono text-figure">{waypointCount(kind.code)}</span>
                            </li>
                        ))}
                    </ul>
                </div>
            )}
        </section>
    )
}

export default Legend
