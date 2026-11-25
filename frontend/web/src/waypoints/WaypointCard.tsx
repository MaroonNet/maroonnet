import { useState, type ReactNode } from 'react'
import Button from '../frame/Button.tsx'
import Card from '../frame/Card.tsx'
import ConfirmBox from '../frame/ConfirmBox.tsx'
import { formatPosition } from '../map/position.ts'
import { useMission } from '../mission/mission.ts'
import { formatTime } from '../mission/missionTime.ts'
import { radioLabel } from '../people/peopleWords.ts'
import MakeProbabilityMap from '../probability/MakeProbabilityMap.tsx'
import { STARTING_KINDS } from '../probability/probability.ts'
import KindMarker from './KindMarker.tsx'
import { kindOf } from './kinds.ts'
import { useWaypoints, type Waypoint } from './waypoints.ts'

type Props = {
    id: number                          // the selected waypoint
    onClose: () => void                 // the card's close button, or the waypoint was deleted: nothing is selected
    onEdit: (id: number) => void        // Edit was pressed
    onMapMade?: () => void              // a probability map was made from this waypoint
}

// The card of the selected waypoint. Shows nothing once it is no longer on the board.
// (A click on several markers on one spot shows map/StackCard.tsx first.)
function WaypointCard({ id, onClose, onEdit, onMapMade = () => {} }: Props) {
    const waypoint = useWaypoints().waypoints.find((one) => one.id === id)
    if (!waypoint) return null
    return <OneWaypoint key={waypoint.id} waypoint={waypoint} onClose={onClose} onEdit={onEdit} onMapMade={onMapMade} />
}

type OneProps = { waypoint: Waypoint, onClose: () => void, onEdit: (id: number) => void, onMapMade: () => void }

// One waypoint's card: its marker and name, its facts, its description and note, and its
// buttons. A waypoint is edited and deleted here and nowhere else. A waypoint a search
// starts out from also has Make Probability Map.
function OneWaypoint({ waypoint, onClose, onEdit, onMapMade }: OneProps) {
    const { mission } = useMission()
    const { remove } = useWaypoints()
    const [asking, setAsking] = useState(false)  // "Delete it?" is on screen
    const [busy, setBusy] = useState(false)      // the delete is on its way
    const [failure, setFailure] = useState('')   // why the delete did not work
    if (!mission) return null
    // A paused or ended session cannot be changed.
    const changeable = mission.status === 'planning' || mission.status === 'active'

    async function deleteIt() {
        setAsking(false)
        setBusy(true)
        const reason = await remove(waypoint.id)
        setBusy(false)
        if (reason) setFailure(reason)
        else onClose()
    }

    return (
        <Card title="Waypoint" onClose={onClose}>
            <div className="flex items-center gap-2">
                <KindMarker kind={waypoint.kind} />
                <p className="text-input font-bold">{waypoint.name}</p>
            </div>
            <dl className="grid grid-cols-[auto_1fr] items-baseline gap-x-3 gap-y-1.5 pt-2.5">
                <Fact label="Kind">{kindOf(waypoint.kind).label}</Fact>
                <Fact label="Position">{formatPosition(waypoint)}</Fact>
                <Fact label="Dropped">{formatTime(waypoint.time, mission.time_zone)}</Fact>
                {waypoint.radio_id !== null && <Fact label="Reported by">{radioLabel(waypoint.radio_id)}</Fact>}
            </dl>
            {waypoint.description && <Words label="Description (sent to teams)">{waypoint.description}</Words>}
            {waypoint.note && <Words label="Note (command post only)">{waypoint.note}</Words>}
            {/* role="alert" has a screen reader read the line out when it appears. */}
            {failure && <p role="alert" className="pt-2 font-medium text-red">{failure}</p>}

            <div className="flex gap-2 pt-3">
                {changeable && <Button disabled={busy} onClick={() => onEdit(waypoint.id)} className="flex-1">Edit</Button>}
                {/* Sending is not built yet, so the button is greyed and does nothing. */}
                <Button aria-disabled title="Not available yet" className="flex-1 opacity-40">Send</Button>
                {changeable && <Button disabled={busy} onClick={() => setAsking(true)} className="flex-1">Delete</Button>}
            </div>

            {/* A map is made while a mission is being planned or run, not once its session has stopped. */}
            {changeable && STARTING_KINDS.includes(waypoint.kind) && <MakeProbabilityMap waypoint={waypoint} onMade={onMapMade} />}

            {asking && (
                <ConfirmBox
                    title={`Delete ${waypoint.name}?`}
                    choices={[
                        { label: 'Keep', onPress: () => setAsking(false) },
                        { label: 'Delete', onPress: deleteIt, main: true },
                    ]}
                >
                    The waypoint is taken off the map. It stays in the mission's record.
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

// A stretch of the waypoint's own words under a small heading.
function Words({ label, children }: { label: string, children: string }) {
    return (
        <div className="pt-2.5">
            <p className="font-mono text-label tracking-widest text-muted uppercase">{label}</p>
            <p className="pt-0.5 whitespace-pre-wrap">{children}</p>
        </div>
    )
}

export default WaypointCard
