import type { ReactNode } from 'react'
import Card from '../frame/Card.tsx'
import { polygonArea } from '../map/geo.ts'
import { useMission } from '../mission/mission.ts'
import { formatTime } from '../mission/missionTime.ts'
import { useSettings } from '../settings/settings.ts'
import { formatArea } from '../settings/units.ts'
import { useSectors } from './sectors.ts'
import { sectorNote, STATUS_LABELS } from './sectorWords.ts'

type Props = {
    id: number              // the selected sector
    onClose: () => void     // the card's close button: nothing is selected
}

// The card of the selected sector: its status, what can be done with it, its area and its
// times. The group, and the times it was assigned and entered, are added with assigning in
// D7. Shows nothing once the sector is no longer on the board.
function SectorCard({ id, onClose }: Props) {
    const { mission } = useMission()
    const { sectors } = useSectors()
    const { units } = useSettings().settings
    const sector = sectors.find((s) => s.id === id)
    if (!sector || !mission) return null
    const zone = mission.time_zone
    return (
        <Card title={`Sector ${sector.name}`} onClose={onClose}>
            <p className="font-mono text-label tracking-widest uppercase">{STATUS_LABELS[sector.status]}</p>
            <p className="pt-1 font-medium text-muted">{sectorNote(sector)}</p>
            <dl className="grid grid-cols-[auto_1fr] items-baseline gap-x-3 gap-y-1.5 pt-2.5">
                <Fact label="Area">{formatArea(polygonArea(sector.corners), units)}</Fact>
                <Fact label="Drawn">{formatTime(sector.created_time, zone)}</Fact>
                {sector.completed_time && <Fact label="Completed">{formatTime(sector.completed_time, zone)}</Fact>}
            </dl>
        </Card>
    )
}

function Fact({ label, children }: { label: string, children: ReactNode }) {
    return (
        <>
            <dt className="font-medium text-muted">{label}</dt>
            <dd className="font-mono text-figure">{children}</dd>
        </>
    )
}

export default SectorCard
