import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import { MissionContext, type OpenMission } from '../mission/mission.ts'
import { SectorsContext, type Sector, type SectorsBoard } from '../sectors/sectors.ts'
import { arizona } from '../teams/sample.ts'
import CommunicationLog from './CommunicationLog.tsx'
import type { LogLine } from './log.ts'
import { ASSIGNED, LINES } from './sample.ts'

afterEach(() => {
    cleanup()
    vi.unstubAllGlobals()
})

// A pretend backend. It keeps the addresses it was asked, and answers each from the list.
function backend(...answers: (LogLine[] | 'fails')[]) {
    const asked: string[] = []
    vi.stubGlobal('fetch', async (address: string) => {
        asked.push(address)
        const answer = answers.shift() ?? []
        if (answer === 'fails') return { ok: false, status: 500, statusText: 'Server Error', json: async () => null }
        return { ok: true, status: 200, statusText: '', json: async () => answer }
    })
    return asked
}

const never = async () => ''
const board = (sectors: Sector[]): SectorsBoard => ({
    sectors, loadedFor: 'az07', add: never, changeShape: never, remove: never, assign: never,
    release: never, markEntered: never, complete: never,
})

function show(mission: OpenMission | null = arizona(), sectors: Sector[] = []) {
    const screenWith = (open: OpenMission | null, list: Sector[]) => (
        <MissionContext value={{ mission: open, loadFailed: false, run: async () => '' }}>
            <SectorsContext value={board(list)}>
                <CommunicationLog />
            </SectorsContext>
        </MissionContext>
    )
    const { rerender } = render(screenWith(mission, sectors))
    return (next: OpenMission | null, list: Sector[] = sectors) => rerender(screenWith(next, list))
}

const openLog = () => fireEvent.click(screen.getByRole('button', { name: 'Open the Communication Log' }))
// The words of each line shown, top to bottom.
const lines = () => within(screen.getByRole('list', { name: 'Log lines' })).getAllByRole('listitem')
    .map((item) => item.getAttribute('aria-label')).filter((words) => words !== null)
const loaded = () => waitFor(() => expect(lines()).toHaveLength(LINES.length))

test('the log is folded when the app opens, and reads nothing until it is opened', () => {
    const asked = backend(LINES)
    show()
    expect(screen.getByRole('button', { name: 'Open the Communication Log' })).toBeTruthy()
    expect(screen.queryByRole('list')).toBeNull()
    expect(asked).toEqual([])
})

test('with no mission open the log cannot be opened', () => {
    const asked = backend(LINES)
    show(null)
    const button = screen.getByRole('button', { name: 'Open the Communication Log' })
    expect(button.getAttribute('aria-disabled')).toBe('true')
    expect(button.title).toBe('Open a mission first')
    fireEvent.click(button)
    expect(screen.queryByRole('list')).toBeNull()
    expect(asked).toEqual([])
})

test('opened, it lists every line, oldest first, with times in the mission time zone', async () => {
    const asked = backend(LINES)
    show()
    openLog()
    await loaded()
    expect(asked).toEqual(['/api/mission/log'])
    expect(lines()).toEqual([
        '8:50 pm · Assignment · S1 assigned to Group 1',
        '11:24 pm · To Radio 4 · Instruction · Radio 4: find a landing zone. · acknowledged 11:24 pm',
        '12:24 am · Assignment · S3 completed by Group 2',
        '12:33 am · From Radio 4 · Evidence · Landing zone marked.',
        '1:51 am · To Radios 1, 2 · Instruction · Move to the helicopter point. · 1 acknowledged',
        '2:34 am · From Radio 1 · Found · Subject located.',
        '2:37 am · Assignment · S4 released by Group 3 (partial)',
        '2:38 am · Broadcast · 3 radios · Instruction · Subject found. All teams return to CP. · 3 acknowledged',
    ])
})

test('the fold button folds it again', async () => {
    backend(LINES)
    show()
    openLog()
    await loaded()
    fireEvent.click(screen.getByRole('button', { name: 'Fold the Communication Log' }))
    expect(screen.queryByRole('list')).toBeNull()
    expect(screen.getByRole('button', { name: 'Open the Communication Log' })).toBeTruthy()
})

test('a type filter shows only its lines, and All shows every line again', async () => {
    backend(LINES)
    show()
    openLog()
    await loaded()

    fireEvent.click(screen.getByRole('button', { name: 'Assignment' }))
    expect(lines()).toEqual([
        '8:50 pm · Assignment · S1 assigned to Group 1',
        '12:24 am · Assignment · S3 completed by Group 2',
        '2:37 am · Assignment · S4 released by Group 3 (partial)',
    ])
    expect(screen.getByRole('button', { name: 'Assignment' }).getAttribute('aria-pressed')).toBe('true')
    expect(screen.getByRole('button', { name: 'All' }).getAttribute('aria-pressed')).toBe('false')

    fireEvent.click(screen.getByRole('button', { name: 'All' }))
    expect(lines()).toHaveLength(LINES.length)
})

test('a filter with no lines says so', async () => {
    backend(LINES)
    show()
    openLog()
    await loaded()
    fireEvent.click(screen.getByRole('button', { name: 'Out of sector' }))
    expect(screen.getByText('No lines of this type.')).toBeTruthy()
})

test('a mission with nothing logged says so', async () => {
    backend([])
    show()
    openLog()
    expect(await screen.findByText('Nothing logged yet.')).toBeTruthy()
})

test('a send to several radios opens to list each radio and when it acknowledged', async () => {
    backend(LINES)
    show()
    openLog()
    await loaded()
    const line = screen.getByRole('button', { name: /To Radios 1, 2/ })
    expect(line.getAttribute('aria-expanded')).toBe('false')

    fireEvent.click(line)

    expect(line.getAttribute('aria-expanded')).toBe('true')
    const radios = within(screen.getByRole('list', { name: 'Radios of this message' })).getAllByRole('listitem')
    expect(radios.map((radio) => radio.textContent)).toEqual(['Radio 1acknowledged 1:51 am', 'Radio 2not acknowledged'])

    fireEvent.click(line)
    expect(screen.queryByRole('list', { name: 'Radios of this message' })).toBeNull()
})

test('the list of radios is scrolled into view when its line opens, since the newest line is at the bottom', async () => {
    const scrolled = vi.fn()
    HTMLElement.prototype.scrollIntoView = scrolled  // the pretend browser has none of its own
    backend(LINES)
    show()
    openLog()
    await loaded()

    fireEvent.click(screen.getByRole('button', { name: /Broadcast · 3 radios/ }))

    expect(scrolled).toHaveBeenCalledTimes(1)
    expect(scrolled.mock.contexts[0]).toBe(screen.getByRole('list', { name: 'Radios of this message' }))
})

test('a message to one radio does not open', async () => {
    backend(LINES)
    show()
    openLog()
    await loaded()
    expect(screen.queryByRole('button', { name: /To Radio 4/ })).toBeNull()
})

test('the send box is greyed', async () => {
    backend(LINES)
    show()
    openLog()
    await loaded()
    const send = screen.getByRole('button', { name: 'Send' })
    expect(send.getAttribute('aria-disabled')).toBe('true')
    expect(send.title).toBe('Not available yet')
    expect((screen.getByRole('textbox', { name: 'Message to send' }) as HTMLInputElement).disabled).toBe(true)
    expect((screen.getByRole('combobox', { name: 'Send to' }) as HTMLSelectElement).disabled).toBe(true)
})

test('the log is read again when the sectors change, since a sector given to a group adds a line', async () => {
    const asked = backend([], [ASSIGNED])
    const change = show(arizona(), [])
    openLog()
    await screen.findByText('Nothing logged yet.')

    change(arizona(), [])  // a new list of sectors, as the board holds after any change

    await waitFor(() => expect(lines()).toEqual(['8:50 pm · Assignment · S1 assigned to Group 1']))
    expect(asked).toHaveLength(2)
})

test("another mission's log is read in its place", async () => {
    const asked = backend(LINES, [])
    const change = show()
    openLog()
    await loaded()

    change({ ...arizona(), id: 'other' })

    expect(await screen.findByText('Nothing logged yet.')).toBeTruthy()
    expect(asked).toHaveLength(2)
})

test('a log that cannot be read says so', async () => {
    backend('fails')
    show()
    openLog()
    expect(await screen.findByText('The log could not be read.')).toBeTruthy()
})
