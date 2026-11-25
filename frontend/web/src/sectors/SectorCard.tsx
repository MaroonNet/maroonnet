import { useState, type ReactNode } from 'react'
import Button from '../frame/Button.tsx'
import Card from '../frame/Card.tsx'
import ConfirmBox from '../frame/ConfirmBox.tsx'
import { polygonArea } from '../map/geo.ts'
import { useMission } from '../mission/mission.ts'
import { formatTime } from '../mission/missionTime.ts'
import { useSettings } from '../settings/settings.ts'
import { formatArea } from '../settings/units.ts'
import { useSectors } from './sectors.ts'
import { sectorNote, STATUS_LABELS } from './sectorWords.ts'

type Props = {
    id: number                      // the selected sector
    onClose: () => void             // the card's close button, or the sector was deleted: nothing is selected
    onEdit: (id: number) => void    // Edit Shape was pressed
}

// The card of the selected sector: its status, what can be done with it, its area and its
// times. A sector that has never been assigned also has Edit Shape and Delete. The group,
// and the times it was assigned and entered, are added with assigning in D7. Shows nothing
// once the sector is no longer on the board.
function SectorCard({ id, onClose, onEdit }: Props) {
    const { mission } = useMission()
    const { sectors, remove } = useSectors()
    const { units } = useSettings().settings
    const [asking, setAsking] = useState(false)  // the box asking before Delete is up
    const [busy, setBusy] = useState(false)      // the delete is on its way
    const [failure, setFailure] = useState('')   // why the delete did not work
    const sector = sectors.find((s) => s.id === id)
    if (!sector || !mission) return null
    const zone = mission.time_zone

    async function deleteIt() {
        setAsking(false)
        setBusy(true)
        const reason = await remove(id)
        setBusy(false)
        if (reason) setFailure(reason)
        else onClose()
    }

    return (
        <Card title={`Sector ${sector.name}`} onClose={onClose}>
            <p className="font-mono text-label tracking-widest uppercase">{STATUS_LABELS[sector.status]}</p>
            <p className="pt-1 font-medium text-muted">{sectorNote(sector)}</p>
            <dl className="grid grid-cols-[auto_1fr] items-baseline gap-x-3 gap-y-1.5 pt-2.5">
                <Fact label="Area">{formatArea(polygonArea(sector.corners), units)}</Fact>
                <Fact label="Drawn">{formatTime(sector.created_time, zone)}</Fact>
                {sector.completed_time && <Fact label="Completed">{formatTime(sector.completed_time, zone)}</Fact>}
            </dl>
            {/* role="alert" has a screen reader read the line out when it appears. */}
            {failure && <p role="alert" className="pt-2 font-medium text-red">{failure}</p>}
            {sector.can_edit && (
                <div className="flex gap-2 pt-3">
                    <Button look="dark" disabled={busy} onClick={() => onEdit(id)} className="flex-1">Edit Shape</Button>
                    <Button disabled={busy} onClick={() => setAsking(true)} className="flex-1">Delete</Button>
                </div>
            )}
            {asking && (
                <ConfirmBox
                    title={`Delete ${sector.name}?`}
                    choices={[
                        { label: 'Keep', onPress: () => setAsking(false) },
                        { label: 'Delete', onPress: deleteIt, main: true },
                    ]}
                >
                    The sector and its shape are removed from the mission. This cannot be undone.
                </ConfirmBox>
            )}
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
