import { cleanup, render, screen, within } from '@testing-library/react'
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

test('the command post radio and the relays are listed first, in their own set', () => {
    show()
    expect(screen.getByText('Command post and relays · 2')).toBeTruthy()
    expect(rows('Command post and relays')).toEqual([
        'Radio 8Command post1564517367Ellen Brandt · No group · Last position 4:20 am',
        'Radio 6Relay1016025774Nobody · No group · No position yet',
    ])
})

test('the searcher radios follow, each with who carries it, its group and its newest position', () => {
    show()
    expect(screen.getByText('Searcher radios · 5')).toBeTruthy()
    expect(rows('Searcher radios')).toEqual([
        'Radio 1Searcher3663644600Marcus Ibarra, Tessa Lindqvist · Group 1 · Last position 4:19 am',
        'Radio 2Searcher1128083228Priya Raman · Group 1 · Last position 4:18 am',
        'Radio 4Searcher2134581666Diego Alas · No group · No position yet',
        'Radio 5Searcher3876229574Nobody · No group · No position yet',
        'Radio 7Searcher2603508945Ana Morales · Group 2 · Last position 4:17 am',
    ])
})

test('a radio carried by more than two people counts the rest', () => {
    const crowded = RADIOS.map((radio) => radio.id === 1
        ? { ...radio, people: [...radio.people, { id: 3, name: 'Owen Whitfield', placeholder: false }, { id: 5, name: 'Dale Kowalski', placeholder: false }] }
        : radio)
    render(
        <MissionContext value={{ mission: arizona(), loadFailed: false, run: async () => '' }}>
            <PeopleContext value={{ roster: [], people: PEOPLE, radios: crowded, groups: GROUPS, run: async () => '' }}>
                <MeshPanel />
            </PeopleContext>
        </MissionContext>,
    )
    expect(rows('Searcher radios')[0]).toBe('Radio 1Searcher3663644600Marcus Ibarra, Tessa Lindqvist +2 · Group 1 · Last position 4:19 am')
})

test('the panel shows no radio health and nothing to press', () => {
    show()
    expect(screen.queryByRole('button')).toBeNull()
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
