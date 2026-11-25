import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import { MissionContext, type MissionStatus } from '../mission/mission.ts'
import { arizona } from '../teams/sample.ts'
import CenterOnCommandPost from './CenterOnCommandPost.tsx'
import { ARIZONA07, board, waypoint } from './sample.ts'
import WaypointCard from './WaypointCard.tsx'
import { WaypointsContext, type WaypointsBoard } from './waypoints.ts'

afterEach(cleanup)

function show(id: number, status: MissionStatus = 'active', changes: Partial<WaypointsBoard> = {}) {
    const on = { close: vi.fn(), edit: vi.fn() }
    render(
        <MissionContext value={{ mission: arizona(status), loadFailed: false, run: async () => '' }}>
            <WaypointsContext value={board(ARIZONA07, changes)}>
                <WaypointCard id={id} onClose={on.close} onEdit={on.edit} />
            </WaypointsContext>
        </MissionContext>,
    )
    return on
}

function facts(): Record<string, string | null> {
    return Object.fromEntries(screen.getAllByRole('term').map((label) => [label.textContent, label.nextElementSibling!.textContent]))
}

test('the card shows the waypoint\'s name, kind, place, time and the radio that reported it', () => {
    show(4)
    expect(screen.getByRole('heading', { name: 'Waypoint' })).toBeTruthy()
    expect(screen.getByText('Boot prints')).toBeTruthy()
    expect(facts()).toEqual({ Kind: 'Evidence', Position: '31.5071 N 110.6693 W', Dropped: '1:37 am', 'Reported by': 'Radio 1' })
})

test('a waypoint the commander placed names no radio', () => {
    show(1)
    expect(facts()).toEqual({ Kind: 'Command post', Position: '31.5063 N 110.6775 W', Dropped: '8:40 pm' })
})

test('the helicopter sighting\'s card shows both its description and its note', () => {
    show(5)
    expect(screen.getByText('Description (sent to teams)').nextElementSibling!.textContent).toBe('Heat signature on FLIR, not yet confirmed on the ground')
    expect(screen.getByText('Note (command post only)').nextElementSibling!.textContent).toBe('Reported by the Border Patrol helicopter')
})

test('a waypoint with no description or note shows neither heading', () => {
    show(1)
    expect(screen.queryByText('Description (sent to teams)')).toBeNull()
    expect(screen.queryByText('Note (command post only)')).toBeNull()
})

test('Send is greyed, since sending is not built', () => {
    show(4)
    const send = screen.getByRole('button', { name: 'Send' })
    expect(send.getAttribute('aria-disabled')).toBe('true')
    expect(send.title).toBe('Not available yet')
})

test('Edit starts the editing of this waypoint', () => {
    const on = show(4)
    fireEvent.click(screen.getByRole('button', { name: 'Edit' }))
    expect(on.edit).toHaveBeenCalledWith(4)
})

test('Delete asks first, then takes the waypoint off the map and closes the card', async () => {
    const remove = vi.fn(async (_id: number) => '')
    const on = show(4, 'active', { remove })
    fireEvent.click(screen.getByRole('button', { name: 'Delete' }))
    const question = screen.getByRole('dialog', { name: 'Delete Boot prints?' })
    expect(remove).not.toHaveBeenCalled()
    fireEvent.click(within(question).getByRole('button', { name: 'Delete' }))
    await waitFor(() => expect(on.close).toHaveBeenCalled())
    expect(remove).toHaveBeenCalledWith(4)
})

test('a delete that is refused shows why, and the card stays', async () => {
    const on = show(4, 'active', { remove: async () => 'There is no waypoint 4 on the map.' })
    fireEvent.click(screen.getByRole('button', { name: 'Delete' }))
    fireEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Delete' }))
    expect((await screen.findByRole('alert')).textContent).toBe('There is no waypoint 4 on the map.')
    expect(on.close).not.toHaveBeenCalled()
})

test.each(['paused', 'ended'] as const)('in a %s session the card has no Edit or Delete', (status) => {
    show(4, status)
    expect(screen.queryByRole('button', { name: 'Edit' })).toBeNull()
    expect(screen.queryByRole('button', { name: 'Delete' })).toBeNull()
})

test('in planning a waypoint can be edited and deleted', () => {
    show(4, 'planning')
    expect(screen.getByRole('button', { name: 'Edit' })).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Delete' })).toBeTruthy()
})

test('a last known position and a point last seen have Make Probability Map, and no other kind does', () => {
    const seen = waypoint(7, 'point_last_seen', 'Seen by hiker')
    const kinds = [...ARIZONA07, seen].map((one) => {
        cleanup()
        render(
            <MissionContext value={{ mission: arizona(), loadFailed: false, run: async () => '' }}>
                <WaypointsContext value={board([...ARIZONA07, seen])}>
                    <WaypointCard id={one.id} onClose={() => {}} onEdit={() => {}} />
                </WaypointsContext>
            </MissionContext>,
        )
        return [one.kind, screen.queryByRole('button', { name: 'Make Probability Map' }) !== null]
    })
    expect(kinds).toEqual([
        ['command_post', false], ['last_known_position', true], ['landing_zone', false], ['evidence', false],
        ['find', false], ['find', false], ['point_last_seen', true],
    ])
})

test.each(['paused', 'ended'] as const)('in a %s session a last known position has no Make Probability Map', (status) => {
    show(2, status)
    expect(screen.queryByRole('button', { name: 'Make Probability Map' })).toBeNull()
})

test('in planning a map can be made from a last known position', () => {
    show(2, 'planning')
    expect(screen.getByRole('button', { name: 'Make Probability Map' })).toBeTruthy()
})

test('a waypoint that is no longer on the board shows no card', () => {
    show(99)
    expect(screen.queryByRole('heading')).toBeNull()
})

// Center on Command Post

function showCenter(waypoints = ARIZONA07) {
    const map = { easeTo: vi.fn() }
    render(
        <WaypointsContext value={board(waypoints)}>
            <CenterOnCommandPost map={map as never} />
        </WaypointsContext>,
    )
    return map
}

test('Center on Command Post moves the map to the command post', () => {
    const map = showCenter()
    fireEvent.click(screen.getByRole('button', { name: 'Center on Command Post' }))
    expect(map.easeTo).toHaveBeenCalledWith({ center: [-110.6775338, 31.5062579] })
})

test('with no command post the button is greyed and says why', () => {
    const map = showCenter([waypoint(2, 'hazard', 'Mine shaft')])
    const button = screen.getByRole('button', { name: 'Center on Command Post' })
    expect(button.getAttribute('aria-disabled')).toBe('true')
    expect(button.title).toBe('No command post is placed')
    fireEvent.click(button)
    expect(map.easeTo).not.toHaveBeenCalled()
})
