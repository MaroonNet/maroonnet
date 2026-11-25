import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import { PeopleContext } from '../people/people.ts'
import { GROUPS, PEOPLE, RADIOS } from '../teams/sample.ts'
import { ARIZONA07, board } from '../waypoints/sample.ts'
import { WaypointsContext } from '../waypoints/waypoints.ts'
import StackCard from './StackCard.tsx'
import type { Stack } from './stacks.ts'

afterEach(cleanup)

function show(stack: Stack) {
    const on = { team: vi.fn(), waypoint: vi.fn(), close: vi.fn() }
    render(
        <PeopleContext value={{ roster: [], people: PEOPLE, radios: RADIOS, groups: GROUPS, run: async () => '' }}>
            <WaypointsContext value={board(ARIZONA07)}>
                <StackCard stack={stack} onPickTeam={on.team} onPickWaypoint={on.waypoint} onClose={on.close} />
            </WaypointsContext>
        </PeopleContext>,
    )
    return on
}

// The card's rows: every button but the close button.
const rows = () => screen.getAllByRole('button').filter((button) => button.getAttribute('aria-label') !== 'Close card')

test('with two waypoints on one spot the card asks which, and a row picks that one', () => {
    const on = show({ teams: [], waypoints: [5, 6] })
    expect(screen.getByRole('heading', { name: '2 Waypoints here' })).toBeTruthy()
    expect(rows().map((row) => row.textContent)).toEqual(['Helicopter sightingFind', 'Subject foundFind'])
    fireEvent.click(rows()[0])
    expect(on.waypoint).toHaveBeenCalledWith(5)
})

test("with teams on one spot the card lists each with its group's dot and its group, and a row picks that team", () => {
    const on = show({ teams: [1, 2, 7], waypoints: [] })
    expect(screen.getByRole('heading', { name: '3 Teams here' })).toBeTruthy()
    expect(rows().map((row) => row.textContent)).toEqual(['Radio 1Group 1', 'Radio 2Group 1', 'Radio 7Group 2'])
    expect(rows()[2].firstElementChild!.className).toContain('size-3.5')
    fireEvent.click(rows()[2])
    expect(on.team).toHaveBeenCalledWith(7)
})

test('teams and waypoints on one spot are listed together, teams first', () => {
    const on = show({ teams: [1, 7], waypoints: [1] })
    expect(screen.getByRole('heading', { name: '2 Teams · 1 Waypoint here' })).toBeTruthy()
    expect(rows().map((row) => row.textContent)).toEqual(['Radio 1Group 1', 'Radio 7Group 2', 'Command postCommand post'])
    fireEvent.click(rows()[2])
    expect(on.waypoint).toHaveBeenCalledWith(1)
    expect(on.team).not.toHaveBeenCalled()
})

test('what is no longer there is left off the list and out of the count', () => {
    show({ teams: [1, 5], waypoints: [1, 99] })  // radio 5 has nobody on it; waypoint 99 was deleted
    expect(screen.getByRole('heading', { name: '1 Team · 1 Waypoint here' })).toBeTruthy()
    expect(rows()).toHaveLength(2)
})

test('a stack with nothing left shows no card', () => {
    show({ teams: [5], waypoints: [99] })
    expect(screen.queryByRole('heading')).toBeNull()
})
