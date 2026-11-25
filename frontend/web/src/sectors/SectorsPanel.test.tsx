import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import { MissionContext, type OpenMission } from '../mission/mission.ts'
import { SettingsContext } from '../settings/settings.ts'
import SectorCard from './SectorCard.tsx'
import { SectorsContext, type Sector } from './sectors.ts'
import SectorsPanel from './SectorsPanel.tsx'

afterEach(cleanup)

const ARIZONA07: OpenMission = {
    id: 'az07', name: 'Arizona07', time_zone: 'America/Phoenix', status: 'ended', session: 1,
    start_time: '2025-04-14T03:30:00Z', end_time: '2025-04-14T11:20:00Z', sessions: [], asks_to_continue: false,
}

const SQUARE = [{ lat: 31.5, lon: -110.7 }, { lat: 31.51, lon: -110.7 }, { lat: 31.51, lon: -110.69 }, { lat: 31.5, lon: -110.69 }]

function sector(id: number, status: Sector['status'], extra: Partial<Sector> = {}): Sector {
    return {
        id, name: `S${id}`, status, group_id: null, can_edit: false, corners: SQUARE,
        created_time: '2025-04-14T03:35:00Z', completed_time: status === 'completed' ? '2025-04-14T08:21:45Z' : null, ...extra,
    }
}

// Arizona07's seven, as they ended (only S7 was never assigned).
const ARIZONA07_SECTORS = [
    sector(1, 'completed'), sector(2, 'completed'), sector(3, 'completed'), sector(4, 'partial'),
    sector(5, 'completed'), sector(6, 'partial'), sector(7, 'drawn', { can_edit: true, created_time: '2025-04-14T08:02:00Z' }),
]

type BoardsProps = { children: React.ReactNode, mission?: OpenMission | null, sectors?: Sector[], remove?: (id: number) => Promise<string> }
function Boards({ children, mission = ARIZONA07, sectors = ARIZONA07_SECTORS, remove = async () => '' }: BoardsProps) {
    return (
        <SettingsContext value={{ settings: { units: 'imperial' }, loadFailed: false, change: async () => false }}>
            <MissionContext value={{ mission, loadFailed: false, run: async () => '' }}>
                <SectorsContext value={{ sectors, loadedFor: mission?.id ?? null, add: async () => '', changeShape: async () => '', remove }}>
                    {children}
                </SectorsContext>
            </MissionContext>
        </SettingsContext>
    )
}

// The panel.

test('the Sectors panel lists every sector with its status and a line about it', () => {
    render(<Boards><SectorsPanel selected={null} onPick={() => {}} /></Boards>)
    const rows = screen.getAllByRole('button')
    expect(rows.map((row) => row.textContent)).toEqual([
        'S1CompletedCompleted 1:21 am', 'S2CompletedCompleted 1:21 am', 'S3CompletedCompleted 1:21 am',
        'S4PartialSearched in part', 'S5CompletedCompleted 1:21 am', 'S6PartialSearched in part', 'S7DrawnUnassigned',
    ])
})

test('pressing a sector in the panel selects it, and the selected one is marked', () => {
    const onPick = vi.fn()
    render(<Boards><SectorsPanel selected={4} onPick={onPick} /></Boards>)

    fireEvent.click(screen.getByRole('button', { name: /^S7/ }))

    expect(onPick).toHaveBeenCalledWith(7)
    expect(screen.getByRole('button', { name: /^S4/ }).getAttribute('aria-current')).toBe('true')
    expect(screen.getByRole('button', { name: /^S7/ }).getAttribute('aria-current')).toBeNull()
})

test('with no mission open, or no sectors yet, the panel says so', () => {
    const { unmount } = render(<Boards mission={null} sectors={[]}><SectorsPanel selected={null} onPick={() => {}} /></Boards>)
    expect(screen.getByText('No mission is open.')).toBeTruthy()
    unmount()

    render(<Boards sectors={[]}><SectorsPanel selected={null} onPick={() => {}} /></Boards>)
    expect(screen.getByText('No sectors yet.')).toBeTruthy()
    expect(screen.getByText(/Pick the Draw Sector tool/)).toBeTruthy()
})

// The card.

// The figure beside a label in the card's list of facts.
const fact = (label: string) => screen.getAllByText(label).find((element) => element.tagName === 'DT')?.nextSibling?.textContent

test("a drawn sector's card: its name, status, what can be done, its area and when it was drawn", () => {
    render(<Boards><SectorCard id={7} onClose={() => {}} onEdit={() => {}} /></Boards>)
    expect(screen.getByRole('heading', { name: 'Sector S7' })).toBeTruthy()
    expect(screen.getAllByText('Drawn').map((element) => element.tagName)).toEqual(['P', 'DT'])  // the status, then the row
    expect(screen.getByText('Not sent yet. Shape can still be edited.')).toBeTruthy()
    expect(fact('Area')).toBe('0.41 mi²')  // 0.01 degree square here: 1.112 km by 0.949 km
    expect(fact('Drawn')).toBe('1:02 am')  // Arizona07's own time zone
})

test("a completed sector's card says it is history and when it was completed", () => {
    render(<Boards><SectorCard id={1} onClose={() => {}} onEdit={() => {}} /></Boards>)
    expect(screen.getByText('History. Kept for the after-action review.')).toBeTruthy()
    expect(fact('Completed')).toBe('1:21 am')
})

test("a partial sector's card says it can be searched again", () => {
    render(<Boards><SectorCard id={4} onClose={() => {}} onEdit={() => {}} /></Boards>)
    expect(screen.getByText('Searched in part. It can be assigned again.')).toBeTruthy()
})

test("a drawn sector that was assigned before says its shape is locked", () => {
    render(<Boards sectors={[sector(8, 'drawn', { can_edit: false })]}><SectorCard id={8} onClose={() => {}} onEdit={() => {}} /></Boards>)
    expect(screen.getByText('Sent before. Shape is locked.')).toBeTruthy()
})

test('the card closes with its close button', () => {
    const onClose = vi.fn()
    render(<Boards><SectorCard id={7} onClose={onClose} onEdit={() => {}} /></Boards>)
    fireEvent.click(screen.getByRole('button', { name: 'Close card' }))
    expect(onClose).toHaveBeenCalledOnce()
})

test('a never-assigned sector has Edit Shape and Delete; a sector that has been used has neither', () => {
    const { unmount } = render(<Boards><SectorCard id={7} onClose={() => {}} onEdit={() => {}} /></Boards>)
    expect(screen.getByRole('button', { name: 'Edit Shape' })).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Delete' })).toBeTruthy()
    unmount()

    render(<Boards><SectorCard id={4} onClose={() => {}} onEdit={() => {}} /></Boards>)
    expect(screen.queryByRole('button', { name: 'Edit Shape' })).toBeNull()
    expect(screen.queryByRole('button', { name: 'Delete' })).toBeNull()
})

test('Edit Shape starts editing that sector', () => {
    const onEdit = vi.fn()
    render(<Boards><SectorCard id={7} onClose={() => {}} onEdit={onEdit} /></Boards>)
    fireEvent.click(screen.getByRole('button', { name: 'Edit Shape' }))
    expect(onEdit).toHaveBeenCalledWith(7)
})

test('Delete asks first; Keep deletes nothing', () => {
    const remove = vi.fn(async () => '')
    render(<Boards remove={remove}><SectorCard id={7} onClose={() => {}} onEdit={() => {}} /></Boards>)

    fireEvent.click(screen.getByRole('button', { name: 'Delete' }))
    expect(screen.getByRole('dialog', { name: 'Delete S7?' })).toBeTruthy()

    fireEvent.click(screen.getByRole('button', { name: 'Keep' }))
    expect(screen.queryByRole('dialog')).toBeNull()
    expect(remove).not.toHaveBeenCalled()
})

test('Delete in the box deletes the sector, and the card closes', async () => {
    const remove = vi.fn(async () => ''), onClose = vi.fn()
    render(<Boards remove={remove}><SectorCard id={7} onClose={onClose} onEdit={() => {}} /></Boards>)

    fireEvent.click(screen.getByRole('button', { name: 'Delete' }))
    fireEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Delete' }))

    await waitFor(() => expect(onClose).toHaveBeenCalledOnce())
    expect(remove).toHaveBeenCalledWith(7)
})

test('a refused delete keeps the card, which says why', async () => {
    const remove = vi.fn(async () => 'This session is ended, so nothing in it can be changed.')
    render(<Boards remove={remove}><SectorCard id={7} onClose={() => {}} onEdit={() => {}} /></Boards>)

    fireEvent.click(screen.getByRole('button', { name: 'Delete' }))
    fireEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Delete' }))

    expect((await screen.findByRole('alert')).textContent).toBe('This session is ended, so nothing in it can be changed.')
    expect(screen.getByRole('heading', { name: 'Sector S7' })).toBeTruthy()
})

test('a sector that is no longer on the board shows no card', () => {
    render(<Boards sectors={[]}><SectorCard id={7} onClose={() => {}} onEdit={() => {}} /></Boards>)
    expect(screen.queryByRole('heading')).toBeNull()
})
