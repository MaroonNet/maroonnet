import { useState, type ReactNode } from 'react'
import Button from '../frame/Button.tsx'
import Card from '../frame/Card.tsx'
import ConfirmBox from '../frame/ConfirmBox.tsx'
import { polygonArea } from '../map/geo.ts'
import { useMission } from '../mission/mission.ts'
import { formatTime } from '../mission/missionTime.ts'
import { usePeople } from '../people/people.ts'
import { groupLabel, radioLabel } from '../people/peopleWords.ts'
import { useSettings } from '../settings/settings.ts'
import { formatArea } from '../settings/units.ts'
import type { Group } from '../teams/teams.ts'
import { carriedBy, groupColor, teamsOf } from '../teams/teamWords.ts'
import { useSectors } from './sectors.ts'
import { sectorNote, sendsLine, standingOf, statusLabel } from './sectorWords.ts'

type Props = {
    id: number                      // the selected sector
    onClose: () => void             // the card's close button, or the sector was deleted: nothing is selected
    onEdit: (id: number) => void    // Edit Shape was pressed
}

// What the card shows under its heading: the sector's facts and buttons, the list of groups
// to give it to, or the list of teams to say which one entered it.
type Showing = 'facts' | 'groups' | 'teams'

// The question on screen before something is done: delete it, mark it completed, or give
// it to a group that holds another sector.
type Question = 'delete' | 'complete' | { busy: Group }

const ROW = 'flex w-full cursor-pointer items-baseline gap-2 rounded-control border border-ink/30 px-2.5 py-1.5 text-left hover:bg-strip'

// The card of the selected sector: its status, what can be done with it, its facts and its
// buttons. A sector is given to a group, released, marked entered and marked completed
// here and nowhere else. A sector that has never been assigned also has Edit Shape and
// Delete. Shows nothing once the sector is no longer on the board.
function SectorCard({ id, onClose, onEdit }: Props) {
    const { mission } = useMission()
    const { sectors, remove, assign, release, markEntered, complete } = useSectors()
    const { groups, radios, run: readPeople } = usePeople()
    const { units } = useSettings().settings
    const [showing, setShowing] = useState<Showing>('facts')
    const [asking, setAsking] = useState<Question | null>(null)
    const [busy, setBusy] = useState(false)      // a change is on its way
    const [failure, setFailure] = useState('')   // why the last change did not work
    const sector = sectors.find((s) => s.id === id)
    if (!sector || !mission) return null
    const zone = mission.time_zone
    const standing = standingOf(sector)
    const held = sector.group_id !== null
    // A paused or ended session cannot be changed. Entering and completing record the
    // search itself, so they wait for Start Mission; assigning can be planned before it.
    const changeable = mission.status === 'planning' || mission.status === 'active'
    const started = mission.status === 'active'
    const teams = teamsOf(radios).filter((radio) => radio.group_id === sector.group_id)  // of the group that holds it
    const groupsWithTeams = groups.filter((group) => group.radio_ids.length > 0)
    const sent = sendsLine(sector.sends)

    // Sends one change. The groups are read again after it, since a group's sector shows in
    // the Groups & Teams panel and on a team's card.
    async function send(change: Promise<string>) {
        setAsking(null)
        setShowing('facts')
        setBusy(true)
        const reason = await change
        if (!reason) await readPeople(Promise.resolve())
        setBusy(false)
        setFailure(reason)
    }

    async function deleteIt() {
        setAsking(null)
        setBusy(true)
        const reason = await remove(id)
        setBusy(false)
        if (reason) setFailure(reason)
        else onClose()
    }

    return (
        <Card title={`Sector ${sector.name}`} onClose={onClose}>
            <p className="font-mono text-label tracking-widest uppercase">{statusLabel(sector)}</p>
            {showing === 'facts' && <>
                <p className="pt-1 font-medium text-muted">{sectorNote(sector)}</p>
                <dl className="grid grid-cols-[auto_1fr] items-baseline gap-x-3 gap-y-1.5 pt-2.5">
                    {sector.group_id !== null && <Fact label="Group"><GroupName id={sector.group_id} /></Fact>}
                    <Fact label="Area">{formatArea(polygonArea(sector.corners), units)}</Fact>
                    <Fact label="Drawn">{formatTime(sector.created_time, zone)}</Fact>
                    {sector.assigned_time && <Fact label="Assigned">{formatTime(sector.assigned_time, zone)}</Fact>}
                    {sector.entered_time && <Fact label="Entered">{formatTime(sector.entered_time, zone)}</Fact>}
                    {sector.completed_time && <Fact label="Completed">{formatTime(sector.completed_time, zone)}</Fact>}
                    {sector.completed_by !== null && <Fact label="Completed by"><GroupName id={sector.completed_by} /></Fact>}
                </dl>
                {sent && <p className="pt-2 font-medium text-muted">{sent}</p>}
            </>}
            {/* role="alert" has a screen reader read the line out when it appears. */}
            {failure && <p role="alert" className="pt-2 font-medium text-red">{failure}</p>}

            {showing === 'facts' && changeable && !held && (standing === 'drawn' || standing === 'partial') && (
                <div className="flex pt-3">
                    <Button look="dark" disabled={busy} onClick={() => setShowing('groups')} className="flex-1">Assign to Group</Button>
                </div>
            )}
            {showing === 'facts' && changeable && held && <>
                {!started && <p className="pt-2 font-medium text-muted">Start the mission to mark it entered or completed.</p>}
                <div className="grid grid-cols-2 gap-2 pt-3">
                    {started && standing === 'assigned' && (
                        <Button
                            look="dark"
                            disabled={busy || teams.length === 0}
                            title={teams.length === 0 ? `${groupLabel(sector.group_id)} has no teams` : 'Temporary: a radio will report this'}
                            onClick={() => teams.length === 1 ? send(markEntered(id, teams[0].id)) : setShowing('teams')}
                        >
                            Mark Entered
                        </Button>
                    )}
                    {started && <Button look={standing === 'searching' ? 'dark' : 'plain'} disabled={busy} onClick={() => setAsking('complete')}>Mark Completed</Button>}
                    <Button disabled={busy} onClick={() => send(release(id))}>Release</Button>
                    {/* Sending is not built yet, so the button is greyed and does nothing. */}
                    <Button aria-disabled title="Not available yet" className="opacity-40">Message</Button>
                </div>
            </>}
            {showing === 'facts' && sector.can_edit && (
                <div className="flex gap-2 pt-3">
                    <Button disabled={busy} onClick={() => onEdit(id)} className="flex-1">Edit Shape</Button>
                    <Button disabled={busy} onClick={() => setAsking('delete')} className="flex-1">Delete</Button>
                </div>
            )}

            {showing === 'groups' && (
                <div className="flex flex-col gap-1.5 pt-2.5">
                    <p className="font-medium text-muted">Assign {sector.name} to</p>
                    {groupsWithTeams.length === 0 && <p>No group has a team yet. Groups are made in Groups & Teams.</p>}
                    {groupsWithTeams.map((group) => (
                        <button
                            key={group.id}
                            type="button"
                            onClick={() => group.sector ? setAsking({ busy: group }) : send(assign(id, group.id))}
                            className={ROW}
                        >
                            <GroupName id={group.id} />{group.sector && <span className="font-medium text-muted"> · holds {group.sector.name}</span>}
                        </button>
                    ))}
                    <Button onClick={() => setShowing('facts')}>Cancel</Button>
                </div>
            )}
            {showing === 'teams' && (
                <div className="flex flex-col gap-1.5 pt-2.5">
                    <p className="font-medium text-muted">Which team entered {sector.name}?</p>
                    {teams.map((team) => (
                        <button key={team.id} type="button" onClick={() => send(markEntered(id, team.id))} className={`${ROW} flex-col gap-0`}>
                            <span>{radioLabel(team.id)}</span>
                            <span className="font-medium text-muted">{carriedBy(team)}</span>
                        </button>
                    ))}
                    <Button onClick={() => setShowing('facts')}>Cancel</Button>
                </div>
            )}

            {asking === 'delete' && (
                <ConfirmBox
                    title={`Delete ${sector.name}?`}
                    choices={[
                        { label: 'Keep', onPress: () => setAsking(null) },
                        { label: 'Delete', onPress: deleteIt, main: true },
                    ]}
                >
                    The sector and its shape are removed from the mission. This cannot be undone.
                </ConfirmBox>
            )}
            {asking === 'complete' && (
                <ConfirmBox
                    title={`Mark ${sector.name} completed?`}
                    choices={[
                        { label: 'Cancel', onPress: () => setAsking(null) },
                        { label: 'Mark Completed', onPress: () => send(complete(id)), main: true },
                    ]}
                >
                    {groupLabel(sector.group_id)} is taken off it. A completed sector is final and cannot be reopened.
                </ConfirmBox>
            )}
            {asking !== null && typeof asking === 'object' && (
                <ConfirmBox
                    title={`Give ${sector.name} to ${groupLabel(asking.busy.id)}?`}
                    choices={[
                        { label: 'Cancel', onPress: () => setAsking(null) },
                        { label: 'Assign', onPress: () => send(assign(id, asking.busy.id)), main: true },
                    ]}
                >
                    {groupLabel(asking.busy.id)} holds {asking.busy.sector?.name}. {asking.busy.sector?.name} will be released, not completed.
                </ConfirmBox>
            )}
        </Card>
    )
}

// A group's name with a dot in its color.
function GroupName({ id }: { id: number }) {
    return (
        <span className="inline-flex items-center gap-1.5">
            <span aria-hidden className="size-2.5 flex-none rounded-full" style={{ background: groupColor(id) }} />
            {groupLabel(id)}
        </span>
    )
}

function Fact({ label, children }: { label: string, children: ReactNode }) {
    return (
        <>
            <dt className="font-medium text-muted">{label}</dt>
            <dd className="tabular-nums">{children}</dd>
        </>
    )
}

export default SectorCard
