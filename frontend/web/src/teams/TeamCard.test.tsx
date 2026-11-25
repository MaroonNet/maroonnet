import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import { MissionContext } from '../mission/mission.ts'
import { PeopleContext } from '../people/people.ts'
import { arizona, GROUPS, PEOPLE, RADIOS } from './sample.ts'
import TeamCard from './TeamCard.tsx'

afterEach(cleanup)

function show(id: number, onClose = vi.fn()) {
    render(
        <MissionContext value={{ mission: arizona(), loadFailed: false, run: async () => '' }}>
            <PeopleContext value={{ roster: [], people: PEOPLE, radios: RADIOS, groups: GROUPS, run: async () => '' }}>
                <TeamCard id={id} onClose={onClose} />
            </PeopleContext>
        </MissionContext>,
    )
    return onClose
}

// What the card says for each label.
function facts(): Record<string, string | null> {
    const labels = screen.getAllByRole('term')
    return Object.fromEntries(labels.map((label) => [label.textContent, label.nextElementSibling!.textContent]))
}

test('the card shows the team\'s searchers, group, sector and newest position', () => {
    show(1)
    expect(screen.getByRole('heading', { name: 'Radio 1' })).toBeTruthy()
    expect(facts()).toEqual({
        Searchers: 'Marcus IbarraTessa Lindqvist',
        Group: 'Group 1',
        Sector: 'S4',
        'Last position': '4:19 am',
        Position: '31.5063 N 110.6775 W',
        Elevation: '4,921 ft',
    })
})

test('a team with no group and no position says so', () => {
    show(4)
    expect(facts()).toEqual({ Searchers: 'Diego Alas', Group: 'No group', Sector: 'None', 'Last position': 'None yet' })
})

test('the card shows facts only: Message is greyed, and nothing moves or edits the team', () => {
    show(1)
    const buttons = screen.getAllByRole('button').map((button) => button.textContent || button.getAttribute('aria-label'))
    expect(buttons).toEqual(['Close card', 'Message'])
    const message = screen.getByRole('button', { name: 'Message' })
    expect(message.getAttribute('aria-disabled')).toBe('true')
    expect(message.getAttribute('title')).toBe('Not available yet')
})

test('a radio that is no longer a team has no card', () => {
    show(5)  // nobody carries radio 5
    expect(screen.queryByRole('heading')).toBeNull()
})
