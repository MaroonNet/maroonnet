import { cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import { afterEach, expect, test } from 'vitest'
import { held, NO_LIFE, sector } from '../sectors/sample.ts'
import { SectorsContext, type Sector } from '../sectors/sectors.ts'
import { ARIZONA07, board } from '../waypoints/sample.ts'
import { WaypointsContext, type Waypoint } from '../waypoints/waypoints.ts'
import Legend from './Legend.tsx'

afterEach(cleanup)

function show(sectors: Sector[], waypoints: Waypoint[] = []) {
    render(
        <SectorsContext value={{ sectors, loadedFor: 'az07', add: async () => '', changeShape: async () => '', remove: async () => '', ...NO_LIFE }}>
            <WaypointsContext value={board(waypoints)}>
                <Legend />
            </WaypointsContext>
        </SectorsContext>,
    )
    fireEvent.click(screen.getByRole('button', { name: 'Show legend' }))
}

// The rows of one of the legend's two lists.
const rows = (list: 'Sectors' | 'Waypoints') =>
    within(screen.getByRole('list', { name: list })).getAllByRole('listitem').map((row) => row.textContent)

test('the legend counts the sectors by status, Partial included', () => {
    // Arizona07 as it ended, then S4 given out again and S6 entered.
    show([
        sector(1, 'completed'), sector(2, 'completed'), sector(3, 'completed'), held(4, 'partial', 3),
        sector(5, 'completed'), held(6, 'searching', 1), sector(7, 'drawn'), sector(8, 'partial'),
    ])
    expect(rows('Sectors')).toEqual(['Drawn1', 'Assigned1', 'Searching1', 'Partial1', 'Completed4'])
})

test('a status with no sectors is still listed, with 0', () => {
    show([sector(7, 'drawn')])
    expect(rows('Sectors')).toEqual(['Drawn1', 'Assigned0', 'Searching0', 'Partial0', 'Completed0'])
})

test('the legend lists all ten waypoint kinds with their counts, 0 included', () => {
    show([sector(7, 'drawn')], ARIZONA07)
    expect(rows('Waypoints')).toEqual([
        'Command post1', 'Last known position1', 'Point last seen0', 'Evidence1', 'Hazard0', 'Landing zone1', 'Find2',
        'Relay0', 'Meeting point0', 'Other0',
    ])
})

test('each waypoint row shows the kind\'s marker', () => {
    show([], ARIZONA07)
    const list = screen.getByRole('list', { name: 'Waypoints' })
    expect(list.querySelectorAll('svg')).toHaveLength(10)
})

test('the legend scrolls inside a third of the screen\'s height, and does not grow past it', () => {
    show([sector(7, 'drawn')], ARIZONA07)
    const legend = screen.getByRole('region', { name: 'Legend' })
    expect(legend.className).toContain('max-h-[33vh]')
    expect(screen.getByRole('list', { name: 'Waypoints' }).parentElement!.className).toContain('overflow-y-auto')
})

test('with no sectors and no waypoints the legend has nothing to show', () => {
    show([])
    expect(screen.getByText('Nothing to show yet.')).toBeTruthy()
    expect(screen.queryByRole('listitem')).toBeNull()
})

test('the legend folds back to its button', () => {
    show([sector(7, 'drawn')])
    fireEvent.click(screen.getByRole('button', { name: 'Collapse legend' }))
    expect(screen.getByRole('button', { name: 'Show legend' })).toBeTruthy()
})
