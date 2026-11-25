import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import { MissionContext, type MissionStatus, type OpenMission } from '../mission/mission.ts'
import ManageRoster from './ManageRoster.tsx'
import { PeopleContext, type Person, type RosterPerson } from './people.ts'

afterEach(() => {
    cleanup()
    vi.unstubAllGlobals()
})

function bearCreek(status: MissionStatus = 'planning'): OpenMission {
    return {
        id: 'bc', name: 'Bear Creek', time_zone: 'America/Denver', status, session: 1, start_time: null,
        end_time: null, sessions: [], asks_to_continue: false,
    }
}

const ROSTER: RosterPerson[] = [
    { id: 2, first_name: 'Ben', middle_initial: null, last_name: 'Cho', phone: '555-0102' },
    { id: 3, first_name: 'Corey', middle_initial: 'B', last_name: 'Greene', phone: null },
    { id: 1, first_name: 'Ana', middle_initial: null, last_name: 'Ruiz', phone: null },
]

function person(id: number, first_name: string, last_name: string, extra: Partial<Person> = {}): Person {
    return {
        id, first_name, last_name, checked_in: true, in_time: '2026-11-20T15:00:00Z', out_time: null,
        in_roster: true, roster_id: null, phone: null, team_id: null, node_num: null, group_id: null,
        shares: [], last_on_radio: false, placeholder: false, can_remove: false, history: [], ...extra,
    }
}

// Ana is checked in, with one placeholder. Ben and Corey are in the roster only.
const PEOPLE = [person(1, 'Ana', 'Ruiz'), person(2, 'Searcher', '#1', { placeholder: true, in_roster: false })]

// Stands in for the backend: every request is noted and answered. refuse names an address
// it answers with a refusal.
function pretendBackend(refuse: Record<string, string> = {}) {
    const sent: { method: string, address: string, body?: unknown }[] = []
    vi.stubGlobal('fetch', vi.fn(async (address: string, request?: RequestInit) => {
        const method = request?.method ?? 'GET'
        sent.push({ method, address, body: request?.body ? JSON.parse(request.body as string) : undefined })
        const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { 'content-type': 'application/json' } })
        if (refuse[address]) return json({ detail: refuse[address] }, 409)
        if (method === 'DELETE') return new Response(null, { status: 204 })
        return json({ id: 9 })  // a person just added has id 9
    }))
    return sent
}

type ShowProps = { mission?: OpenMission | null, roster?: RosterPerson[], people?: Person[], onClose?: () => void }
function show({ mission = bearCreek(), roster = ROSTER, people = PEOPLE, onClose = () => {} }: ShowProps = {}) {
    // The board waits for the request, as the real one does, and reads nothing again.
    const run = async (request: Promise<unknown>) => request.then(() => '', (error: Error) => error.message)
    return render(
        <MissionContext value={{ mission, loadFailed: false, run: async () => '' }}>
            <PeopleContext value={{ roster, people: mission ? people : [], run }}>
                <ManageRoster onClose={onClose} />
            </PeopleContext>
        </MissionContext>,
    )
}

const rosterList = () => within(screen.getByRole('list', { name: 'Roster' }))
const checkedInList = () => within(screen.getByRole('list', { name: 'Checked in' }))

test('the dialog lists who is checked in, and everyone in the roster', () => {
    pretendBackend()
    show()
    expect(screen.getByRole('dialog', { name: 'Manage Roster' })).toBeTruthy()
    expect(screen.getByText('Checked in · 2')).toBeTruthy()
    expect(checkedInList().getAllByRole('listitem').map((row) => row.textContent)).toEqual(['Ana Ruiz', 'Searcher #1Placeholder'])
    expect(screen.getByText('Roster · 3')).toBeTruthy()
    expect(rosterList().getAllByRole('listitem').map((row) => row.textContent)).toEqual([
        'Ben Cho+ Check in', 'Corey B. Greene+ Check in', 'Ana RuizChecked in',
    ])
    expect(screen.getByText('1 checked in · 1 placeholder')).toBeTruthy()
})

test('the search box narrows the roster', () => {
    pretendBackend()
    show()
    fireEvent.change(screen.getByPlaceholderText('Search by name'), { target: { value: 'gre' } })
    expect(rosterList().getAllByRole('listitem').map((row) => row.textContent)).toEqual(['Corey B. Greene+ Check in'])
    fireEvent.change(screen.getByPlaceholderText('Search by name'), { target: { value: 'zzz' } })
    expect(screen.getByText('No one in the roster matches "zzz".')).toBeTruthy()
})

test('+ Check in checks a roster person in to the mission', async () => {
    const sent = pretendBackend()
    show()
    fireEvent.click(screen.getByRole('button', { name: 'Check in Ben Cho' }))
    await waitFor(() => expect(sent).toEqual([{ method: 'POST', address: '/api/mission/people/check-in', body: { roster_id: 2 } }]))
})

test('a refused check-in shows the reason', async () => {
    pretendBackend({ '/api/mission/people/check-in': 'Ben Cho is already checked in.' })
    show()
    fireEvent.click(screen.getByRole('button', { name: 'Check in Ben Cho' }))
    expect((await screen.findByRole('alert')).textContent).toBe('Ben Cho is already checked in.')
})

test('Add Placeholder adds one to the mission', async () => {
    const sent = pretendBackend()
    show()
    fireEvent.click(screen.getByRole('button', { name: 'Add Placeholder' }))
    await waitFor(() => expect(sent).toEqual([{ method: 'POST', address: '/api/mission/people/placeholders', body: undefined }]))
})

test('with no mission open the dialog is the roster alone', () => {
    pretendBackend()
    show({ mission: null })
    expect(screen.queryByText(/^Checked in ·/)).toBeNull()
    expect(screen.queryByRole('button', { name: 'Add Placeholder' })).toBeNull()
    expect(screen.queryByRole('button', { name: /^Check in / })).toBeNull()
    expect(screen.getByText('3 in the roster')).toBeTruthy()
})

test('a paused session shows who was checked in, and takes no check-in', () => {
    pretendBackend()
    show({ mission: bearCreek('paused') })
    expect(screen.getByText('Checked in · 2')).toBeTruthy()
    expect(screen.queryByRole('button', { name: 'Add Placeholder' })).toBeNull()
    expect(screen.queryByRole('button', { name: /^Check in / })).toBeNull()
})

test('Add Someone New adds a person to the roster and checks them in', async () => {
    const sent = pretendBackend()
    show()
    fireEvent.click(screen.getByRole('button', { name: 'Add Someone New' }))
    expect(screen.getByText('They are added to the roster and checked in to this mission.')).toBeTruthy()
    const add = screen.getByRole('button', { name: 'Add and Check In' }) as HTMLButtonElement
    expect(add.disabled).toBe(true)  // a first and last name are needed

    fireEvent.change(screen.getByLabelText('First name'), { target: { value: 'Cy' } })
    fireEvent.change(screen.getByLabelText('Middle initial'), { target: { value: 'd' } })
    fireEvent.change(screen.getByLabelText('Last name'), { target: { value: 'Dunn' } })
    fireEvent.change(screen.getByLabelText('Phone number'), { target: { value: '555-0103' } })
    fireEvent.click(add)

    await waitFor(() => expect(sent).toEqual([
        { method: 'POST', address: '/api/roster', body: { first_name: 'Cy', middle_initial: 'd', last_name: 'Dunn', phone: '555-0103' } },
        { method: 'POST', address: '/api/mission/people/check-in', body: { roster_id: 9 } },
    ]))
    // Back on the lists once it is saved.
    await screen.findByText('Roster · 3')
})

test('with no mission open, Add Someone New adds to the roster only', async () => {
    const sent = pretendBackend()
    show({ mission: null })
    fireEvent.click(screen.getByRole('button', { name: 'Add Someone New' }))
    expect(screen.getByText('They are added to the roster for future missions.')).toBeTruthy()
    fireEvent.change(screen.getByLabelText('First name'), { target: { value: 'Cy' } })
    fireEvent.change(screen.getByLabelText('Last name'), { target: { value: 'Dunn' } })
    fireEvent.click(screen.getByRole('button', { name: 'Add to Roster' }))
    await waitFor(() => expect(sent.map((request) => request.address)).toEqual(['/api/roster']))
})

test('a name already in the roster is refused with the reason, and the form stays', async () => {
    pretendBackend({ '/api/roster': 'Ana Ruiz is already in the roster. Add a middle initial to tell them apart.' })
    show({ mission: null })
    fireEvent.click(screen.getByRole('button', { name: 'Add Someone New' }))
    fireEvent.change(screen.getByLabelText('First name'), { target: { value: 'Ana' } })
    fireEvent.change(screen.getByLabelText('Last name'), { target: { value: 'Ruiz' } })
    fireEvent.click(screen.getByRole('button', { name: 'Add to Roster' }))
    expect((await screen.findByRole('alert')).textContent).toMatch(/^Ana Ruiz is already in the roster/)
    expect(screen.getByLabelText('First name')).toBeTruthy()
})

test('pressing a roster person shows their details', () => {
    pretendBackend()
    show()
    fireEvent.click(screen.getByRole('button', { name: 'Ben Cho' }))
    expect(screen.getByRole('heading', { name: 'Ben Cho' })).toBeTruthy()
    expect(screen.getByText('555-0102')).toBeTruthy()
    expect(screen.getByText('In the roster, not checked in to this mission.')).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: 'Back' }))
    expect(screen.getByText('Roster · 3')).toBeTruthy()
})

test('Edit changes a roster person', async () => {
    const sent = pretendBackend()
    show()
    fireEvent.click(screen.getByRole('button', { name: 'Corey B. Greene' }))
    expect(screen.getByText('Not on file')).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: 'Edit' }))
    expect((screen.getByLabelText('Middle initial') as HTMLInputElement).value).toBe('B')
    fireEvent.change(screen.getByLabelText('Phone number'), { target: { value: '555-0199' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save' }))
    await waitFor(() => expect(sent).toEqual([
        { method: 'PUT', address: '/api/roster/3', body: { first_name: 'Corey', middle_initial: 'B', last_name: 'Greene', phone: '555-0199' } },
    ]))
})

test('Delete asks first, then deletes the roster person', async () => {
    const sent = pretendBackend()
    show()
    fireEvent.click(screen.getByRole('button', { name: 'Ben Cho' }))
    fireEvent.click(screen.getByRole('button', { name: 'Delete' }))
    const box = within(screen.getByRole('dialog', { name: 'Delete Ben Cho?' }))
    expect(sent).toEqual([])
    fireEvent.click(box.getByRole('button', { name: 'Delete' }))
    await waitFor(() => expect(sent).toEqual([{ method: 'DELETE', address: '/api/roster/2', body: undefined }]))
    await screen.findByText('Roster · 3')  // back on the lists
})

test('a refused delete shows the reason on the person', async () => {
    pretendBackend({ '/api/roster/1': 'Ana Ruiz is checked in to this mission. Check them out first.' })
    show()
    fireEvent.click(screen.getByRole('button', { name: 'Ana Ruiz' }))
    expect(screen.getByText('Checked in to Bear Creek.')).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: 'Delete' }))
    fireEvent.click(within(screen.getByRole('dialog', { name: 'Delete Ana Ruiz?' })).getByRole('button', { name: 'Delete' }))
    expect((await screen.findByRole('alert')).textContent).toBe('Ana Ruiz is checked in to this mission. Check them out first.')
})

test('Done closes the dialog', () => {
    pretendBackend()
    const onClose = vi.fn()
    show({ onClose })
    fireEvent.click(screen.getByRole('button', { name: 'Done' }))
    expect(onClose).toHaveBeenCalled()
})
