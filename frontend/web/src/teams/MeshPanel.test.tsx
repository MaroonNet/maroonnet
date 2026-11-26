import { cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import { afterEach, expect, test } from 'vitest'
import { MissionContext, type OpenMission } from '../mission/mission.ts'
import { PeopleContext } from '../people/people.ts'
import MeshPanel from './MeshPanel.tsx'
import { arizona, GROUPS, PEOPLE, RADIOS } from './sample.ts'

afterEach(cleanup)

function show(mission: OpenMission | null = arizona()) {
    render(
        <MissionContext value={{ mission, loadFailed: false, run: async () => '' }}>
            <PeopleContext value={{ roster: [], people: mission ? PEOPLE : [], radios: mission ? RADIOS : [], groups: mission ? GROUPS : [], run: async () => '' }}>
                <MeshPanel />
            </PeopleContext>
        </MissionContext>,
    )
}

const rows = (name: string) => within(screen.getByRole('list', { name })).getAllByRole('listitem').map((row) => row.textContent)
const arrow = (radio: number) => screen.getByRole('button', { name: `Details of Radio ${radio}` })

test('the searcher radios come first, each with its group and the time of its last position', () => {
    show()
    expect(screen.getAllByRole('heading').map((heading) => heading.textContent)).toEqual(['Searcher radios · 5', 'Command post and relays · 2'])
    expect(rows('Searcher radios')).toEqual([
        'Radio 1Group 14:19 am', 'Radio 2Group 14:18 am', 'Radio 4No group–', 'Radio 5No group–', 'Radio 7Group 24:17 am',
    ])
})

test('the command post radio and the relays follow in their own set, each with its kind', () => {
    show()
    expect(rows('Command post and relays')).toEqual(['Radio 8Command post4:20 am', 'Radio 6Relay–'])
})

test("each set's columns are labeled, so the time reads as the last position", () => {
    show()
    expect(screen.getAllByText('Last position')).toHaveLength(2)
    expect(screen.getByText('Group')).toBeTruthy()
    expect(screen.getByText('Kind')).toBeTruthy()
})

test("a radio's arrow shows who carries it, one name per line, and its node number, and hides them again", () => {
    show()
    expect(arrow(1).getAttribute('aria-expanded')).toBe('false')
    fireEvent.click(arrow(1))
    expect(arrow(1).getAttribute('aria-expanded')).toBe('true')
    const radio1 = within(screen.getByRole('list', { name: 'Searcher radios' }).firstElementChild as HTMLElement)
    expect(radio1.getByText('Carried by')).toBeTruthy()
    expect(radio1.getByText('Marcus Ibarra')).toBeTruthy()
    expect(radio1.getByText('Tessa Lindqvist')).toBeTruthy()
    expect(radio1.getByText('Node')).toBeTruthy()
    expect(radio1.getByText('3663644600')).toBeTruthy()
    fireEvent.click(arrow(1))
    expect(screen.queryByText('Marcus Ibarra')).toBeNull()
})

test('the details of a radio nobody carries say so', () => {
    show()
    fireEvent.click(arrow(6))
    expect(screen.getByText('Nobody')).toBeTruthy()
    expect(screen.getByText('1016025774')).toBeTruthy()
})

test("the panel shows no radio health, and its only buttons open a radio's details", () => {
    show()
    expect(screen.getAllByRole('button').map((button) => button.getAttribute('aria-label'))).toEqual(
        [1, 2, 4, 5, 7, 8, 6].map((radio) => `Details of Radio ${radio}`))
    expect(screen.queryByText(/batt|heard|in contact/i)).toBeNull()
})

test('with no mission open the panel says so', () => {
    show(null)
    expect(screen.getByText('No mission is open.')).toBeTruthy()
})

test('a mission with no radios says where they come from', () => {
    render(
        <MissionContext value={{ mission: arizona(), loadFailed: false, run: async () => '' }}>
            <MeshPanel />
        </MissionContext>,
    )
    expect(screen.getByText('This mission has no radios.')).toBeTruthy()
})
