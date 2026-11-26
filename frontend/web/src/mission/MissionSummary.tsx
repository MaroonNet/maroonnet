import { polygonArea } from '../map/geo.ts'
import { usePeople } from '../people/people.ts'
import { groupLabel } from '../people/peopleWords.ts'
import { useSectors } from '../sectors/sectors.ts'
import { statusLabel } from '../sectors/sectorWords.ts'
import { useSettings } from '../settings/settings.ts'
import { formatArea } from '../settings/units.ts'
import { teamsOf } from '../teams/teamWords.ts'
import { commandPost } from '../waypoints/waypointWords.ts'
import { useWaypoints } from '../waypoints/waypoints.ts'
import { formatPosition } from '../map/position.ts'

const LABEL = 'font-mono text-label tracking-widest text-muted uppercase'

// The Mission panel's overview of the open mission: how many people are checked in, how
// many teams, groups, sectors and waypoints there are, where the command post is, and a
// table of the sectors. It only shows; a sector is picked on the map or in the Sectors
// panel, and the command post is placed with the Drop Waypoint tool.
function MissionSummary() {
    const { people, radios, groups } = usePeople()
    const { sectors } = useSectors()
    const { units } = useSettings().settings
    const { waypoints } = useWaypoints()
    const post = commandPost(waypoints)
    const checkedIn = people.filter((person) => person.checked_in).length

    return (
        <div className="mt-4 border-t border-ink/20 px-4 pt-3">
            <dl className="grid grid-cols-[auto_1fr] items-center gap-x-3 gap-y-1.5">
                <dt className={LABEL}>People</dt><dd>{checkedIn} checked in</dd>
                <dt className={LABEL}>Teams</dt><dd>{teamsOf(radios).length}</dd>
                <dt className={LABEL}>Groups</dt><dd>{groups.length}</dd>
                <dt className={LABEL}>Sectors</dt><dd>{sectors.length}</dd>
                <dt className={LABEL}>Waypoints</dt><dd>{waypoints.length}</dd>
                <dt className={LABEL}>Command post</dt>
                <dd className={post ? 'tabular-nums' : 'font-medium text-muted'}>{post ? formatPosition(post) : 'Not placed'}</dd>
            </dl>
            {sectors.length > 0 && (
                <table className="mt-3 w-full text-left">
                    <thead>
                        <tr className={LABEL}>
                            <th className="pb-1 font-normal">Sector</th>
                            <th className="pb-1 font-normal">Status</th>
                            <th className="pb-1 font-normal">Group</th>
                            <th className="pb-1 text-right font-normal">Area</th>
                        </tr>
                    </thead>
                    <tbody>
                        {sectors.map((sector) => {
                            // A completed sector names the group that completed it.
                            const group = sector.group_id ?? sector.completed_by
                            return (
                                <tr key={sector.id} className="border-t border-ink/10">
                                    <td className="py-1 tabular-nums">{sector.name}</td>
                                    <td className="py-1">{statusLabel(sector)}</td>
                                    <td className={`py-1 ${group === null ? 'font-medium text-muted' : ''}`}>{group === null ? 'None' : groupLabel(group)}</td>
                                    <td className="py-1 text-right tabular-nums">{formatArea(polygonArea(sector.corners), units)}</td>
                                </tr>
                            )
                        })}
                    </tbody>
                </table>
            )}
        </div>
    )
}

export default MissionSummary
