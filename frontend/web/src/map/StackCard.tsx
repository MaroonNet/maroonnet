import Card from '../frame/Card.tsx'
import { usePeople } from '../people/people.ts'
import { groupLabel, radioLabel } from '../people/peopleWords.ts'
import TeamMarker from '../teams/TeamMarker.tsx'
import { teamsOnMap } from '../teams/teamWords.ts'
import KindMarker from '../waypoints/KindMarker.tsx'
import { kindOf } from '../waypoints/kinds.ts'
import { useWaypoints } from '../waypoints/waypoints.ts'
import { stackWords, type Stack } from './stacks.ts'

type Props = {
    stack: Stack                            // the teams and waypoints one click picked
    onPickTeam: (id: number) => void        // a team's row was pressed
    onPickWaypoint: (id: number) => void    // a waypoint's row was pressed
    onClose: () => void                     // the card's close button
}

const ROW = 'flex w-full cursor-pointer items-center gap-2 rounded-control border border-ink/30 px-2.5 py-1.5 text-left hover:bg-strip'

// The card of a click on several markers on the same spot. It has a row for each team and
// each waypoint there, teams first, and pressing a row shows that one's card. What has
// since left the map is left off. Shows nothing once nothing of the stack is left.
function StackCard({ stack, onPickTeam, onPickWaypoint, onClose }: Props) {
    const teams = teamsOnMap(usePeople().radios).filter((team) => stack.teams.includes(team.id))
    const waypoints = useWaypoints().waypoints.filter((waypoint) => stack.waypoints.includes(waypoint.id))
    if (teams.length + waypoints.length === 0) return null
    return (
        <Card title={`${stackWords(teams.length, waypoints.length)} here`} onClose={onClose}>
            <div className="flex flex-col gap-1.5">
                {teams.map((team) => (
                    <button key={`team-${team.id}`} type="button" onClick={() => onPickTeam(team.id)} className={ROW}>
                        <TeamMarker radio={team} small />
                        <span className="flex-1">{radioLabel(team.id)}</span>
                        <span className="font-medium text-muted">{groupLabel(team.group_id)}</span>
                    </button>
                ))}
                {waypoints.map((waypoint) => (
                    <button key={`waypoint-${waypoint.id}`} type="button" onClick={() => onPickWaypoint(waypoint.id)} className={ROW}>
                        <KindMarker kind={waypoint.kind} small />
                        <span className="flex-1">{waypoint.name}</span>
                        <span className="font-medium text-muted">{kindOf(waypoint.kind).label}</span>
                    </button>
                ))}
            </div>
        </Card>
    )
}

export default StackCard
