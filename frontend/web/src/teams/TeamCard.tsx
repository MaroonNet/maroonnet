import type { ReactNode } from 'react'
import Button from '../frame/Button.tsx'
import Card from '../frame/Card.tsx'
import { formatPosition } from '../map/position.ts'
import { useMission } from '../mission/mission.ts'
import { formatTime } from '../mission/missionTime.ts'
import { usePeople } from '../people/people.ts'
import { groupLabel, radioLabel } from '../people/peopleWords.ts'
import { useSettings } from '../settings/settings.ts'
import { formatElevation } from '../settings/units.ts'
import { groupColor, teamsOf } from './teamWords.ts'

type Props = {
    id: number              // the radio of the selected team
    onClose: () => void     // the card's close button
}

// The card of the selected team: who carries its radio, its group, the sector that group
// holds, and its newest position. It shows facts only. A team is changed from the Edit Team
// form in the Groups & Teams panel, and sending a message is not built yet. Shows nothing
// once the radio is no longer a team.
function TeamCard({ id, onClose }: Props) {
    const { mission } = useMission()
    const { radios, groups } = usePeople()
    const { units } = useSettings().settings
    const radio = teamsOf(radios).find((team) => team.id === id)
    if (!radio || !mission) return null
    const sector = groups.find((group) => group.id === radio.group_id)?.sector
    const position = radio.last_position

    return (
        <Card title="Team" onClose={onClose}>
            <h3 className="text-title font-bold">{radioLabel(radio.id)}</h3>
            <dl className="grid grid-cols-[auto_1fr] items-baseline gap-x-3 gap-y-1.5 pt-2.5">
                <Fact label="Searchers">
                    {radio.people.map((person) => <span key={person.id} className="block">{person.name}</span>)}
                </Fact>
                <Fact label="Group">
                    <span className="inline-flex items-center gap-1.5">
                        {radio.group_id !== null && (
                            <span aria-hidden className="size-2.5 flex-none rounded-full" style={{ background: groupColor(radio.group_id) }} />
                        )}
                        {groupLabel(radio.group_id)}
                    </span>
                </Fact>
                <Fact label="Sector">{sector?.name ?? 'None'}</Fact>
                <Fact label="Last position">{position ? formatTime(position.time, mission.time_zone) : 'None yet'}</Fact>
                {position && <Fact label="Position">{formatPosition(position)}</Fact>}
                {position && position.elevation !== null && <Fact label="Elevation">{formatElevation(position.elevation, units)}</Fact>}
            </dl>
            <div className="flex pt-3">
                {/* Sending is not built yet, so the button is greyed and does nothing. */}
                <Button aria-disabled title="Not available yet" className="flex-1 opacity-40">Message</Button>
            </div>
        </Card>
    )
}

function Fact({ label, children }: { label: string, children: ReactNode }) {
    return (
        <>
            <dt className="font-medium text-muted">{label}</dt>
            <dd>{children}</dd>
        </>
    )
}

export default TeamCard
