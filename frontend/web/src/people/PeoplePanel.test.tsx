import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import { MissionContext, type MissionStatus, type OpenMission } from '../mission/mission.ts'
import { PeopleContext, type Person, type RosterPerson } from './people.ts'
import PeoplePanel from './PeoplePanel.tsx'

afterEach(() => {
    cleanup()
    vi.unstubAllGlobals()
})

// Arizona times: 8:30 pm on April 13, 2025 is 03:30 UTC on April 14.
function arizona(status: MissionStatus = 'active'): OpenMission {
    return {
        id: 'az07', name: 'Arizona07', time_zone: 'America/Phoenix', status, session: 1,
        start_time: '2025-04-14T03:30:00Z', end_time: null, sessions: [], asks_to_continue: false,
    }
}

function person(id: number, first_name: string, last_name: string, extra: Partial<Person> = {}): Person {
    return {
        id, first_name, last_name, checked_in: true, in_time: '2025-04-14T03:30:28Z', out_time: null,
        in_roster: true, roster_id: id, phone: null, team_id: null, node_num: null, group_id: null,
        shares: [], last_on_radio: false, placeholder: false, can_remove: false,
        history: [{ time: '2025-04-14T03:30:28Z', what: 'checked_in', team_id: null }], ...extra,
    }
}

const MARCUS = person(1, 'Marcus', 'Ibarra', {
    phone: '555-0101', team_id: 1, node_num: 101, group_id: 1, shares: ['Tessa Lindqvist', 'Owen Whitfield'],
    history: [
        { time: '2025-04-14T03:30:28Z', what: 'checked_in', team_id: null },
        { time: '2025-04-14T03:50:00Z', what: 'took_radio', team_id: 1 },
    ],
})
const ELLEN = person(16, 'Ellen', 'Brandt', { team_id: 8, node_num: 108, last_on_radio: true })
const NAOMI = person(9, 'Naomi', 'Feld')
const STAND_IN = person(22, 'Searcher', '#1', { placeholder: true, can_remove: true, in_roster: false, roster_id: null })
// Not checked in: Wes left at 1:10 am; Mei was carried from the last session and is in no roster.
const WES = person(17, 'Wes', 'Hallam', { checked_in: false, out_time: '2025-04-14T08:10:00Z' })
const MEI = person(20, 'Mei', 'Tanaka', { checked_in: false, in_time: null, in_roster: false, roster_id: null, history: [] })
const PEOPLE = [MARCUS, NAOMI, ELLEN, WES, MEI, STAND_IN]

const ROSTER: RosterPerson[] = [
    { id: 30, first_name: 'Ben', middle_initial: null, last_name: 'Cho', phone: null },
    { id: 1, first_name: 'Marcus', middle_initial: null, last_name: 'Ibarra', phone: '555-0101' },
]

// Stands in for the backend: every request is noted and answered.
function pretendBackend(refuse: Record<string, string> = {}) {
    const sent: { method: string, address: string, body?: unknown }[] = []
    vi.stubGlobal('fetch', vi.fn(async (address: string, request?: RequestInit) => {
        const method = request?.method ?? 'GET'
        sent.push({ method, address, body: request?.body ? JSON.parse(request.body as string) : undefined })
        const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { 'content-type': 'application/json' } })
        if (refuse[address]) return json({ detail: refuse[address] }, 409)
        if (method === 'DELETE') return new Response(null, { status: 204 })
        return json({})
    }))
    return sent
}

function show(mission: OpenMission | null = arizona(), people: Person[] = PEOPLE) {
    const run = async (request: Promise<unknown>) => request.then(() => '', (error: Error) => error.message)
    return render(
        <MissionContext value={{ mission, loadFailed: false, run: async () => '' }}>
            <PeopleContext value={{ roster: ROSTER, people: mission ? people : [], radios: [], groups: [], run }}>
                <PeoplePanel />
            </PeopleContext>
        </MissionContext>,
    )
}

const list = (name: string) => within(screen.getByRole('list', { name }))

// The panel's lists.

test('the panel lists the people checked in, with what each carries', () => {
    pretendBackend()
    show()
    expect(screen.getByText('Checked in · 4')).toBeTruthy()
    expect(list('Checked in').getAllByRole('listitem').map((row) => row.textContent)).toEqual([
        'Ellen BrandtRadio 8 · No group', 'Naomi FeldNo radio', 'Marcus IbarraRadio 1 · Group 1', 'Searcher #1Placeholder',
    ])
})

test('people who are in the mission and not checked in have their own list', () => {
    pretendBackend()
    show()
    expect(screen.getByText('Not checked in · 2')).toBeTruthy()
    expect(list('Not checked in').getAllByRole('listitem').map((row) => row.textContent)).toEqual([
        'Wes HallamChecked out 1:10 amCheck In', 'Mei TanakaNot yet this sessionCheck In',
    ])
})

test('the search box narrows both lists', () => {
    pretendBackend()
    show()
    fireEvent.change(screen.getByPlaceholderText('Search by name'), { target: { value: 'ha' } })
    expect(screen.queryByRole('list', { name: 'Checked in' })).toBeNull()
    expect(list('Not checked in').getAllByRole('listitem')).toHaveLength(1)
    fireEvent.change(screen.getByPlaceholderText('Search by name'), { target: { value: 'zzz' } })
    expect(screen.getByText('No one matches "zzz".')).toBeTruthy()
})

test('with no mission open the panel still offers the roster', () => {
    pretendBackend()
    show(null)
    expect(screen.getByText('No mission is open. Manage Roster edits the roster; people are checked in once a mission is open.')).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: 'Manage Roster' }))
    expect(screen.getByRole('dialog', { name: 'Manage Roster' })).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: 'Done' }))
    expect(screen.queryByRole('dialog')).toBeNull()
})

test('a mission with nobody says how to check people in', () => {
    pretendBackend()
    show(arizona('planning'), [])
    expect(screen.getByText('No one is checked in yet. Use Manage Roster to check people in.')).toBeTruthy()
})

// Check In, from the Not checked in list.

test('Check In checks in someone who is in the roster, with no question', async () => {
    const sent = pretendBackend()
    show()
    fireEvent.click(screen.getByRole('button', { name: 'Check in Wes Hallam' }))
    await waitFor(() => expect(sent).toEqual([{ method: 'POST', address: '/api/mission/people/17/check-in', body: undefined }]))
    expect(screen.queryByRole('dialog')).toBeNull()
})

test('checking in someone who is not in the roster asks about saving them to it', async () => {
    const sent = pretendBackend()
    show()
    fireEvent.click(screen.getByRole('button', { name: 'Check in Mei Tanaka' }))
    const box = within(await screen.findByRole('dialog', { name: 'Save Mei Tanaka to the roster?' }))
    expect(sent.map((request) => request.address)).toEqual(['/api/mission/people/20/check-in'])

    fireEvent.click(box.getByRole('button', { name: 'Save to Roster' }))
    await waitFor(() => expect(sent.map((request) => request.address)).toEqual([
        '/api/mission/people/20/check-in', '/api/mission/people/20/save-to-roster',
    ]))
    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())
})

test('"Not now" leaves the person out of the roster', async () => {
    const sent = pretendBackend()
    show()
    fireEvent.click(screen.getByRole('button', { name: 'Check in Mei Tanaka' }))
    fireEvent.click(within(await screen.findByRole('dialog')).getByRole('button', { name: 'Not now' }))
    expect(screen.queryByRole('dialog')).toBeNull()
    expect(sent).toHaveLength(1)
})

test('a paused session offers no Check In', () => {
    pretendBackend()
    show(arizona('paused'))
    expect(screen.queryByRole('button', { name: /^Check in / })).toBeNull()
})

// The person view.

test('pressing a person shows their phone, what they carry and their history', () => {
    pretendBackend()
    show()
    fireEvent.click(screen.getByRole('button', { name: /^Marcus Ibarra/ }))
    expect(screen.getByRole('heading', { name: 'Marcus Ibarra' })).toBeTruthy()
    expect(screen.getByText('555-0101')).toBeTruthy()
    expect(screen.getByText('Checked in 8:30 pm')).toBeTruthy()
    const facts = screen.getByRole('group', { name: 'Carrying' }).textContent
    expect(facts).toBe('RadioRadio 1GroupGroup 1Shared withTessa Lindqvist, Owen Whitfield')
    expect(list('History').getAllByRole('listitem').map((row) => row.textContent)).toEqual([
        '8:30 pmChecked in', '8:50 pmStarted carrying Radio 1',
    ])
    fireEvent.click(screen.getByRole('button', { name: 'Back to People' }))
    expect(screen.getByText('Checked in · 4')).toBeTruthy()
})

test('a person with no radio says so', () => {
    pretendBackend()
    show()
    fireEvent.click(screen.getByRole('button', { name: /^Naomi Feld/ }))
    expect(screen.getByText('No radio. Not on a team.')).toBeTruthy()
    expect(screen.getByText('No phone on file')).toBeTruthy()
})

test('Check Out of Mission checks the person out', async () => {
    const sent = pretendBackend()
    show()
    fireEvent.click(screen.getByRole('button', { name: /^Marcus Ibarra/ }))
    fireEvent.click(screen.getByRole('button', { name: 'Check Out of Mission' }))
    await waitFor(() => expect(sent).toEqual([{ method: 'POST', address: '/api/mission/people/1/check-out', body: undefined }]))
})

test('checking out a radio\'s only searcher warns first', async () => {
    const sent = pretendBackend()
    show()
    fireEvent.click(screen.getByRole('button', { name: /^Ellen Brandt/ }))
    fireEvent.click(screen.getByRole('button', { name: 'Check Out of Mission' }))
    const box = within(screen.getByRole('dialog', { name: 'Check out Ellen Brandt?' }))
    expect(box.getByText('Ellen Brandt is the only searcher on Radio 8. Checking out leaves the radio with nobody on it.')).toBeTruthy()
    expect(sent).toEqual([])
    fireEvent.click(box.getByRole('button', { name: 'Check Out' }))
    await waitFor(() => expect(sent.map((request) => request.address)).toEqual(['/api/mission/people/16/check-out']))
})

test('the warning names the group the radio would leave', () => {
    pretendBackend()
    show(arizona(), [{ ...ELLEN, group_id: 2 }])
    fireEvent.click(screen.getByRole('button', { name: /^Ellen Brandt/ }))
    fireEvent.click(screen.getByRole('button', { name: 'Check Out of Mission' }))
    expect(screen.getByText('Ellen Brandt is the only searcher on Radio 8. Checking out leaves the radio with nobody on it, and the radio leaves Group 2.')).toBeTruthy()
})

test('a refused check-out shows the reason', async () => {
    pretendBackend({ '/api/mission/people/1/check-out': 'Marcus Ibarra is not checked in.' })
    show()
    fireEvent.click(screen.getByRole('button', { name: /^Marcus Ibarra/ }))
    fireEvent.click(screen.getByRole('button', { name: 'Check Out of Mission' }))
    expect((await screen.findByRole('alert')).textContent).toBe('Marcus Ibarra is not checked in.')
})

test('someone not checked in has no Check Out, and their view says when they left', () => {
    pretendBackend()
    show()
    fireEvent.click(screen.getByRole('button', { name: 'Wes Hallam' }))
    expect(screen.getByText('Checked out 1:10 am')).toBeTruthy()
    expect(screen.queryByRole('button', { name: 'Check Out of Mission' })).toBeNull()
})

test('an ended session shows both times and changes nothing', () => {
    pretendBackend()
    show(arizona('ended'), [{ ...MARCUS, out_time: '2025-04-14T11:20:00Z' }])
    fireEvent.click(screen.getByRole('button', { name: /^Marcus Ibarra/ }))
    expect(screen.getByText('Checked in 8:30 pm · Checked out 4:20 am')).toBeTruthy()
    expect(screen.queryByRole('button', { name: 'Check Out of Mission' })).toBeNull()
})

test('someone who is not in the roster can be saved to it from their view', async () => {
    const sent = pretendBackend()
    show()
    fireEvent.click(screen.getByRole('button', { name: 'Mei Tanaka' }))
    expect(screen.getByText('Not in the roster.')).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: 'Save to Roster' }))
    await waitFor(() => expect(sent).toEqual([{ method: 'POST', address: '/api/mission/people/20/save-to-roster', body: undefined }]))
})

test('a person in the roster has no Save to Roster', () => {
    pretendBackend()
    show()
    fireEvent.click(screen.getByRole('button', { name: /^Marcus Ibarra/ }))
    expect(screen.queryByRole('button', { name: 'Save to Roster' })).toBeNull()
})

// Placeholders.

test('a placeholder is replaced with a roster person who is not checked in', async () => {
    const sent = pretendBackend()
    show()
    fireEvent.click(screen.getByRole('button', { name: /^Searcher #1/ }))
    expect(screen.getByText('Placeholder for a searcher who is not known yet. Replace it with a real person; they keep its team and radio.')).toBeTruthy()
    expect(screen.queryByRole('button', { name: 'Save to Roster' })).toBeNull()
    const pick = screen.getByLabelText('Replace with') as HTMLSelectElement
    // Marcus is checked in, so only Ben is offered.
    expect([...pick.options].map((option) => option.textContent)).toEqual(['Replace with…', 'Ben Cho'])
    fireEvent.change(pick, { target: { value: '30' } })
    await waitFor(() => expect(sent).toEqual([{ method: 'POST', address: '/api/mission/people/22/replace', body: { roster_id: 30 } }]))
})

test('a placeholder that never carried a radio can be removed, after a question', async () => {
    const sent = pretendBackend()
    show()
    fireEvent.click(screen.getByRole('button', { name: /^Searcher #1/ }))
    fireEvent.click(screen.getByRole('button', { name: 'Remove' }))
    fireEvent.click(within(screen.getByRole('dialog', { name: 'Remove Searcher #1?' })).getByRole('button', { name: 'Remove' }))
    await waitFor(() => expect(sent).toEqual([{ method: 'DELETE', address: '/api/mission/people/22', body: undefined }]))
})

test('a placeholder that carried a radio has no Remove', () => {
    pretendBackend()
    show(arizona(), [{ ...STAND_IN, can_remove: false, team_id: 4 }])
    fireEvent.click(screen.getByRole('button', { name: /^Searcher #1/ }))
    expect(screen.queryByRole('button', { name: 'Remove' })).toBeNull()
    expect(screen.getByLabelText('Replace with')).toBeTruthy()
})
