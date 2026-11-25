import { useMission } from '../mission/mission.ts'
import { useSectors } from './sectors.ts'
import { sectorLine, STATUS_LABELS } from './sectorWords.ts'

const NOTE = 'px-4 pt-3 font-medium text-muted'  // a line said in place of the list

type Props = {
    selected: number | null         // the id of the selected sector
    onPick: (id: number) => void    // a sector was pressed
}

// What the Sectors panel shows: every sector of the open mission, with its status and a
// line about it. Pressing one selects it, as a click on it on the map does. It only lists;
// a sector is drawn with the toolbar's tool.
function SectorsPanel({ selected, onPick }: Props) {
    const { mission } = useMission()
    const { sectors } = useSectors()

    if (!mission) return <p className={NOTE}>No mission is open.</p>
    if (!sectors.length) {
        return (
            <>
                <p className="px-4 pt-3">No sectors yet.</p>
                <p className="px-4 pt-1 font-medium text-muted">
                    Pick the Draw Sector tool on the toolbar, then drag a rectangle on the map. Right-click the tool for a custom shape.
                </p>
            </>
        )
    }
    return (
        <ul className="py-1.5">
            {sectors.map((sector) => (
                <li key={sector.id}>
                    <button
                        type="button"
                        aria-current={sector.id === selected ? true : undefined}
                        onClick={() => onPick(sector.id)}
                        className={`flex w-full cursor-pointer items-baseline gap-3 px-4 py-1.5 text-left ${sector.id === selected ? 'bg-strip' : 'hover:bg-strip'}`}
                    >
                        <span className="w-8 font-mono text-figure">{sector.name}</span>
                        <span className="flex flex-col">
                            <span>{STATUS_LABELS[sector.status]}</span>
                            <span className="font-medium text-muted">{sectorLine(sector, mission.time_zone)}</span>
                        </span>
                    </button>
                </li>
            ))}
        </ul>
    )
}

export default SectorsPanel
