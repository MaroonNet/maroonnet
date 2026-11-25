import { cleanup, render, screen, within } from '@testing-library/react'
import { afterEach, expect, test } from 'vitest'
import { PeopleContext } from '../people/people.ts'
import { held, NO_LIFE, sector } from '../sectors/sample.ts'
import { SectorsContext, type Sector } from '../sectors/sectors.ts'
import { SettingsContext } from '../settings/settings.ts'
import { GROUPS, PEOPLE, RADIOS } from '../teams/sample.ts'
import MissionSummary from './MissionSummary.tsx'

afterEach(cleanup)

// The team tests' mission: nine people, eight of them checked in; Radios 1, 2, 4 and 7 are
// teams; three groups.
function show(sectors: Sector[]) {
    render(
        <SettingsContext value={{ settings: { units: 'imperial' }, loadFailed: false, change: async () => false }}>
            <PeopleContext value={{ roster: [], people: PEOPLE, radios: RADIOS, groups: GROUPS, run: async () => '' }}>
                <SectorsContext value={{ sectors, loadedFor: 'az07', add: async () => '', changeShape: async () => '', remove: async () => '', ...NO_LIFE }}>
                    <MissionSummary />
                </SectorsContext>
            </PeopleContext>
        </SettingsContext>,
    )
}

function facts(): Record<string, string | null> {
    return Object.fromEntries(screen.getAllByRole('term').map((label) => [label.textContent, label.nextElementSibling!.textContent]))
}

test('the summary counts the people checked in, the teams, the groups and the sectors', () => {
    show([sector(1, 'completed'), sector(7, 'drawn')])
    expect(facts()).toEqual({ People: '8 checked in', Teams: '4', Groups: '3', Sectors: '2' })
})

test('the table has a row for each sector: its name, status, group and area', () => {
    show([sector(1, 'completed', { completed_by: 2 }), held(4, 'partial', 1), held(5, 'searching', 2), sector(7, 'drawn')])
    const rows = within(screen.getByRole('table')).getAllByRole('row').map((row) =>
        within(row).getAllByRole(row.querySelector('th') ? 'columnheader' : 'cell').map((cell) => cell.textContent))
    expect(rows).toEqual([
        ['Sector', 'Status', 'Group', 'Area'],
        ['S1', 'Completed', 'Group 2', '0.41 mi²'],  // the group that completed it
        ['S4', 'Assigned', 'Group 1', '0.41 mi²'],
        ['S5', 'Searching', 'Group 2', '0.41 mi²'],
        ['S7', 'Drawn', 'None', '0.41 mi²'],
    ])
})

test('the rows only show: nothing in the table can be pressed', () => {
    show([sector(7, 'drawn')])
    expect(screen.queryByRole('button')).toBeNull()
})

test('with no sectors there is no table', () => {
    show([])
    expect(facts().Sectors).toBe('0')
    expect(screen.queryByRole('table')).toBeNull()
})
