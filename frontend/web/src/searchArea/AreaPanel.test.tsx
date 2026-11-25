import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, expect, test } from 'vitest'
import { MissionContext, type OpenMission } from '../mission/mission.ts'
import { SettingsContext, type Units } from '../settings/settings.ts'
import AreaPanel from './AreaPanel.tsx'
import { SearchAreaContext, type SearchArea } from './searchArea.ts'

afterEach(cleanup)

const ARIZONA07: OpenMission = {
    id: 'az07', name: 'Arizona07', time_zone: 'America/Phoenix', status: 'paused', session: 1,
    start_time: null, end_time: null, sessions: [], asks_to_continue: false,
}
const ARIZONA07_AREA: SearchArea = { min_lat: 31.3926, min_lon: -110.8083, max_lat: 31.619, max_lon: -110.544 }

// Draws the panel with a mission, a search area and a Units setting on their boards.
function drawPanel(mission: OpenMission | null, area: SearchArea | null, units: Units = 'imperial') {
    render(
        <SettingsContext value={{ settings: { units }, loadFailed: false, change: async () => false }}>
            <MissionContext value={{ mission, loadFailed: false, run: async () => '' }}>
                <SearchAreaContext value={{ area, loadedFor: mission?.id ?? null, save: async () => '' }}>
                    <AreaPanel />
                </SearchAreaContext>
            </MissionContext>
        </SettingsContext>,
    )
}

// The figure written beside a label.
const beside = (label: string) => screen.getByText(label).nextSibling?.textContent

test("the panel reads Arizona07's bounds and size", () => {
    drawPanel(ARIZONA07, ARIZONA07_AREA)
    expect(beside('North')).toBe('31.6190 N')
    expect(beside('South')).toBe('31.3926 N')
    expect(beside('West')).toBe('110.8083 W')
    expect(beside('East')).toBe('110.5440 W')
    expect(beside('Width')).toBe('15.6 mi')
    expect(beside('Height')).toBe('15.6 mi')
    expect(beside('Area')).toBe('243.55 mi²')
})

test('the size follows the Units setting', () => {
    drawPanel(ARIZONA07, ARIZONA07_AREA, 'metric')
    expect(beside('Width')).toBe('25.1 km')
    expect(beside('Height')).toBe('25.2 km')
    expect(beside('Area')).toBe('630.79 km²')
})

test('a mission with no search area says how to draw one', () => {
    drawPanel(ARIZONA07, null)
    expect(screen.getByText('No search area yet.')).toBeTruthy()
    expect(screen.getByText(/Draw Search Area tool/)).toBeTruthy()
    expect(screen.queryByText('North')).toBeNull()
    expect(screen.queryByRole('button')).toBeNull()  // the tool is started from the toolbar only
})

test('with no mission open the panel says so', () => {
    drawPanel(null, null)
    expect(screen.getByText('No mission is open.')).toBeTruthy()
})
