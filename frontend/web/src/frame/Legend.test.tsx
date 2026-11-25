import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, expect, test } from 'vitest'
import { held, NO_LIFE, sector } from '../sectors/sample.ts'
import { SectorsContext, type Sector } from '../sectors/sectors.ts'
import Legend from './Legend.tsx'

afterEach(cleanup)

function show(sectors: Sector[]) {
    render(
        <SectorsContext value={{ sectors, loadedFor: 'az07', add: async () => '', changeShape: async () => '', remove: async () => '', ...NO_LIFE }}>
            <Legend />
        </SectorsContext>,
    )
    fireEvent.click(screen.getByRole('button', { name: 'Show legend' }))
}

test('the legend counts the sectors by status, Partial included', () => {
    // Arizona07 as it ended, then S4 given out again and S6 entered.
    show([
        sector(1, 'completed'), sector(2, 'completed'), sector(3, 'completed'), held(4, 'partial', 3),
        sector(5, 'completed'), held(6, 'searching', 1), sector(7, 'drawn'), sector(8, 'partial'),
    ])
    expect(screen.getAllByRole('listitem').map((row) => row.textContent)).toEqual([
        'Drawn1', 'Assigned1', 'Searching1', 'Partial1', 'Completed4',
    ])
})

test('a status with no sectors is still listed, with 0', () => {
    show([sector(7, 'drawn')])
    expect(screen.getAllByRole('listitem').map((row) => row.textContent)).toEqual([
        'Drawn1', 'Assigned0', 'Searching0', 'Partial0', 'Completed0',
    ])
})

test('with no sectors the legend has nothing to show', () => {
    show([])
    expect(screen.getByText('Nothing to show yet.')).toBeTruthy()
    expect(screen.queryByRole('listitem')).toBeNull()
})

test('the legend folds back to its button', () => {
    show([sector(7, 'drawn')])
    fireEvent.click(screen.getByRole('button', { name: 'Collapse legend' }))
    expect(screen.getByRole('button', { name: 'Show legend' })).toBeTruthy()
})
