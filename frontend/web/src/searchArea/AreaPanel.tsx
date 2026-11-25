import type { ReactNode } from 'react'
import { rectangleSize } from '../map/geo.ts'
import { formatLatitude, formatLongitude } from '../map/position.ts'
import { useMission } from '../mission/mission.ts'
import { HEADING } from '../mission/MissionList.tsx'
import { useSettings } from '../settings/settings.ts'
import { formatArea, formatDistance } from '../settings/units.ts'
import { useSearchArea } from './searchArea.ts'

const NOTE = 'px-4 pt-3 font-medium text-muted'  // a line said in place of the facts

// What the Area panel shows: the open mission's search area, as its four bounds and its
// size. It only shows; a search area is drawn, or drawn again, with the toolbar's tool.
function AreaPanel() {
    const { mission } = useMission()
    const { area } = useSearchArea()
    const { units } = useSettings().settings

    if (!mission) return <p className={NOTE}>No mission is open.</p>
    if (!area) {
        return (
            <>
                <p className="px-4 pt-3">No search area yet.</p>
                <p className="px-4 pt-1 font-medium text-muted">
                    Pick the Draw Search Area tool on the toolbar, then drag a rectangle on the map.
                </p>
            </>
        )
    }
    const size = rectangleSize(area)
    return (
        <div className="pt-1.5 pb-2.5">
            <h3 className={HEADING}>Bounds</h3>
            <Facts>
                <Fact label="North">{formatLatitude(area.max_lat)}</Fact>
                <Fact label="South">{formatLatitude(area.min_lat)}</Fact>
                <Fact label="West">{formatLongitude(area.min_lon)}</Fact>
                <Fact label="East">{formatLongitude(area.max_lon)}</Fact>
            </Facts>
            <h3 className={HEADING}>Size</h3>
            <Facts>
                <Fact label="Width">{formatDistance(size.width, units)}</Fact>
                <Fact label="Height">{formatDistance(size.height, units)}</Fact>
                <Fact label="Area">{formatArea(size.area, units)}</Fact>
            </Facts>
        </div>
    )
}

// A list of facts: each label with its figure beside it. The labels' column has one width,
// so the figures of both lists line up.
function Facts({ children }: { children: ReactNode }) {
    return <dl className="grid grid-cols-[3.25rem_1fr] items-baseline gap-x-3 gap-y-1.5 px-4 pt-1">{children}</dl>
}

function Fact({ label, children }: { label: string, children: ReactNode }) {
    return (
        <>
            <dt className="font-medium text-muted">{label}</dt>
            <dd className="font-mono text-figure">{children}</dd>
        </>
    )
}

export default AreaPanel
