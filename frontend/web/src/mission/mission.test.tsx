import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import App from '../App.tsx'
import type { Mission, OpenMission } from './mission.ts'
import MissionProvider from './MissionProvider.tsx'

// The real map needs the backend and a real browser, so the tests draw a box in its place.
vi.mock('../map/MissionMap.tsx', () => ({ default: () => <div data-testid="map" /> }))
vi.mock('../map/mapStyle.ts', () => ({ styleError: '', style: { metadata: { groups: [], trail_uses: [] } } }))

afterEach(() => {
    cleanup()
    vi.unstubAllGlobals()
    vi.useRealTimers()
})

// Arizona07 as the backend lists it: one session, 8:30 pm April 13 to 4:20 am April 14, 2025.
const ARIZONA07: Mission = {
    id: 'az07', name: 'Arizona07', time_zone: 'America/Phoenix', status: 'ended', session: 1,
    start_time: '2025-04-14T03:30:00Z', end_time: '2025-04-14T11:20:00Z',
    sessions: [{ number: 1, status: 'ended', start_time: '2025-04-14T03:30:00Z', end_time: '2025-04-14T11:20:00Z' }],
}

// Bear Creek in each status. Its session started at 8 am on November 20, 2026, Mountain time.
const STARTED = '2026-11-20T15:00:00Z'
const PRESSED = '2026-11-20T23:30:00Z'  // the pretend backend's clock: 4:30 pm
function bearCreek(status: Mission['status'], asks_to_continue = false): OpenMission {
    const start_time = status === 'planning' ? null : STARTED
    const end_time = status === 'paused' || status === 'ended' ? '2026-11-20T22:00:00Z' : null
    return {
        id: 'bc', name: 'Bear Creek', time_zone: 'America/Denver', status, session: 1, start_time, end_time,
        sessions: [{ number: 1, status, start_time, end_time }], asks_to_continue,
    }
}

function jsonAnswer(body: unknown, status = 200): Response {
    return new Response(JSON.stringify(body), { status, headers: { 'content-type': 'application/json' } })
}

// Stands in for the backend's mission routes. missions is what its missions folder holds
// and open is the open mission. refuse names an address the backend answers with a refusal.
// The list it returns fills with each request that changes something.
function pretendBackend(missions: Mission[], open: OpenMission | null = null, refuse: Record<string, string> = {}) {
    const sent: { method: string, address: string, body?: unknown }[] = []
    // Changes the open mission and its latest session together, as the backend's facts do.
    function change(facts: Partial<OpenMission>) {
        open = { ...open!, ...facts }
        const { status, start_time, end_time } = open
        if (status !== 'active') open.asks_to_continue = false  // nothing left to ask
        open.sessions = [...open.sessions.slice(0, -1), { number: open.session, status, start_time, end_time }]
    }
    vi.stubGlobal('fetch', vi.fn(async (address: string, request?: RequestInit) => {
        const method = request?.method ?? 'GET'
        const body = request?.body ? JSON.parse(request.body as string) : undefined
        if (method === 'GET') {
            if (address === '/api/missions') return jsonAnswer(missions)
            if (address === '/api/mission') return jsonAnswer(open)
            return new Response(null, { status: 204 })
        }
        if (!address.startsWith('/api/mission')) return new Response(null, { status: 204 })  // the error log
        sent.push(body === undefined ? { method, address } : { method, address, body })
        if (refuse[address]) return jsonAnswer({ detail: refuse[address] }, 409)

        const opened = /^\/api\/missions\/(.+)\/open$/.exec(address)
        if (opened) open = { ...missions.find((mission) => mission.id === opened[1])!, asks_to_continue: false }
        else if (address === '/api/missions') {
            open = { ...bearCreek('planning'), id: 'new', name: body.name, time_zone: body.time_zone }
            missions.push(open)
        }
        else if (address === '/api/mission/close') { open = null; return new Response(null, { status: 204 }) }
        else if (address === '/api/mission/start') change({ status: 'active', start_time: PRESSED })
        else if (address === '/api/mission/end-session') change({ status: 'paused', end_time: PRESSED })
        else if (address === '/api/mission/end') change({ status: 'ended', end_time: open!.end_time ?? PRESSED })
        else if (address === '/api/mission/resume') change({ status: 'active', end_time: null })
        else if (address === '/api/mission/reopen') change({ status: 'paused' })
        else if (address === '/api/mission/continue') change({ asks_to_continue: false })
        else if (address === '/api/mission/next-session') {
            const session = { number: open!.session + 1, status: 'active' as const, start_time: PRESSED, end_time: null }
            open = { ...open!, ...session, session: session.number, sessions: [...open!.sessions, session] }
        }
        else if (address === '/api/mission') change(body)  // PATCH: the time zone
        return jsonAnswer(open)
    }))
    return sent
}

// Draws the app as main.tsx does and opens the Mission panel.
async function openMissionPanel() {
    render(<MissionProvider><App /></MissionProvider>)
    fireEvent.click(await screen.findByRole('button', { name: /^Mission/ }))
}

function press(name: string | RegExp, inside: HTMLElement = document.body) {
    fireEvent.click(within(inside).getByRole('button', { name }))
}

// The value beside a label in the panel's list of facts.
function fact(label: string): string | null {
    return screen.getByText(label, { selector: 'dt' }).nextElementSibling!.textContent
}

// With no mission open

test('with no mission open the rail reads "Mission + New" and the panel lists every mission with its status', async () => {
    pretendBackend([ARIZONA07, bearCreek('planning')])
    await openMissionPanel()

    expect(screen.getByRole('button', { name: /^Mission/ }).textContent).toBe('Mission+ New')
    expect(screen.getByRole('heading', { name: 'Mission' })).toBeTruthy()
    expect(await screen.findByRole('button', { name: 'Arizona07 · Ended' })).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Bear Creek · Planning' })).toBeTruthy()
})

test('with no missions the list says so, and the New Mission form is there', async () => {
    pretendBackend([])
    await openMissionPanel()

    expect(await screen.findByText('No missions yet.')).toBeTruthy()
    expect(screen.getByRole('heading', { name: 'New Mission' })).toBeTruthy()
    expect(screen.getByRole('textbox', { name: 'Name' })).toBeTruthy()
    const zones = within(screen.getByRole('combobox', { name: 'Time zone' })).getAllByRole('option')
    expect(zones.map((zone) => zone.textContent)).toEqual(
        ['Eastern', 'Central', 'Mountain', 'Arizona', 'Pacific', 'Alaska', 'Hawaii'])
})

test('pressing a mission in the list opens it, and its times are shown in its own time zone', async () => {
    const sent = pretendBackend([ARIZONA07])
    await openMissionPanel()

    fireEvent.click(await screen.findByRole('button', { name: 'Arizona07 · Ended' }))  // waits for the list

    expect(await screen.findByRole('heading', { name: 'Arizona07' })).toBeTruthy()
    expect(sent).toEqual([{ method: 'POST', address: '/api/missions/az07/open' }])
    expect(fact('Status')).toBe('Ended')
    expect(fact('Session')).toBe('Day 1 · Session 1')
    expect(fact('Started')).toBe('Apr 13, 2025, 8:30 pm')
    expect(fact('Ended')).toBe('Apr 14, 2025, 4:20 am')
    expect(screen.getByRole('button', { name: /^Mission/ }).textContent).toBe('Arizona07Day 1 · Session 1')
})

test('the mission that was open is shown when the app opens', async () => {
    pretendBackend([ARIZONA07], { ...ARIZONA07, asks_to_continue: false })
    await openMissionPanel()

    expect(screen.getByRole('heading', { name: 'Arizona07' })).toBeTruthy()
})

// Creating

test('Create Mission sends the name and the picked time zone, and the new mission is open in planning', async () => {
    const sent = pretendBackend([])
    await openMissionPanel()
    const create = await screen.findByRole('button', { name: 'Create Mission' }) as HTMLButtonElement
    expect(create.disabled).toBe(true)  // nothing to create until there is a name

    fireEvent.change(screen.getByRole('textbox', { name: 'Name' }), { target: { value: 'Bear Creek' } })
    fireEvent.change(screen.getByRole('combobox', { name: 'Time zone' }), { target: { value: 'America/Denver' } })
    fireEvent.click(create)

    expect(await screen.findByRole('heading', { name: 'Bear Creek' })).toBeTruthy()
    expect(sent).toEqual([{ method: 'POST', address: '/api/missions', body: { name: 'Bear Creek', time_zone: 'America/Denver' } }])
    expect(fact('Status')).toBe('Planning')
    expect(fact('Started')).toBe('Not started')
    expect(screen.getByRole('button', { name: /^Mission/ }).textContent).toBe('Bear CreekPlanning')
})

test('a refusal from the backend is shown in the panel', async () => {
    pretendBackend([], null, { '/api/missions': 'The missions folder cannot be written.' })
    await openMissionPanel()

    fireEvent.change(await screen.findByRole('textbox', { name: 'Name' }), { target: { value: 'Bear Creek' } })
    press('Create Mission')

    expect((await screen.findByRole('alert')).textContent).toBe('The missions folder cannot be written.')
})

// The buttons for each status

test('a mission in planning has Start Mission, which makes it active', async () => {
    const sent = pretendBackend([], bearCreek('planning'))
    await openMissionPanel()

    press('Start Mission')

    await waitFor(() => expect(fact('Status')).toBe('Active'))
    expect(sent).toEqual([{ method: 'POST', address: '/api/mission/start' }])
    expect(fact('Started')).toBe('Nov 20, 2026, 4:30 pm')
})

test('an active mission shows the time since it started, counting up', async () => {
    vi.useFakeTimers({ toFake: ['Date'] })  // only the clock is pretend, so the rest runs as usual
    vi.setSystemTime(new Date('2026-11-20T15:30:05Z'))
    pretendBackend([], bearCreek('active'))
    await openMissionPanel()

    expect(fact('Elapsed')).toBe('0:30:05')
})

test('End Session asks first, and Cancel ends nothing', async () => {
    const sent = pretendBackend([], bearCreek('active'))
    await openMissionPanel()

    press('End Session')
    const box = screen.getByRole('dialog', { name: 'End Session 1?' })
    press('Cancel', box)

    expect(screen.queryByRole('dialog')).toBeNull()
    expect(sent).toEqual([])
    expect(fact('Status')).toBe('Active')
})

test('End Session, confirmed, pauses the session and offers Resume, the next session and End Mission', async () => {
    const sent = pretendBackend([], bearCreek('active'))
    await openMissionPanel()

    press('End Session')
    press('End Session', screen.getByRole('dialog'))

    await waitFor(() => expect(fact('Status')).toBe('Paused'))
    expect(sent).toEqual([{ method: 'POST', address: '/api/mission/end-session' }])
    expect(screen.queryByRole('dialog')).toBeNull()
    expect(fact('Ended')).toBe('Nov 20, 2026, 4:30 pm')
    for (const name of ['Resume Session 1', 'Start Session 2', 'End Mission']) {
        expect(screen.getByRole('button', { name })).toBeTruthy()
    }
})

test('End Mission asks first, then ends the mission and offers Reopen', async () => {
    const sent = pretendBackend([], bearCreek('active'))
    await openMissionPanel()

    press('End Mission')
    expect(sent).toEqual([])
    press('End Mission', screen.getByRole('dialog', { name: 'End the mission?' }))

    await waitFor(() => expect(fact('Status')).toBe('Ended'))
    expect(sent).toEqual([{ method: 'POST', address: '/api/mission/end' }])
    expect(screen.getByRole('button', { name: 'Reopen' })).toBeTruthy()
    expect(screen.queryByRole('button', { name: 'End Session' })).toBeNull()
})

test('Resume Session puts a paused session back to active', async () => {
    const sent = pretendBackend([], bearCreek('paused'))
    await openMissionPanel()

    press('Resume Session 1')

    await waitFor(() => expect(fact('Status')).toBe('Active'))
    expect(sent).toEqual([{ method: 'POST', address: '/api/mission/resume' }])
})

test('Reopen makes an ended mission paused', async () => {
    const sent = pretendBackend([], { ...ARIZONA07, asks_to_continue: false })
    await openMissionPanel()

    press('Reopen')

    await waitFor(() => expect(fact('Status')).toBe('Paused'))
    expect(sent).toEqual([{ method: 'POST', address: '/api/mission/reopen' }])
    expect(screen.getByRole('button', { name: 'Start Session 2' })).toBeTruthy()
})

// The next session

test.each([
    ['Keep teams as they ended', true],
    ['Start with no teams', false],
])('Start Session 2 asks about teams, and "%s" starts it', async (choice, keep_teams) => {
    const sent = pretendBackend([], bearCreek('paused'))
    await openMissionPanel()

    press('Start Session 2')
    press(choice, screen.getByRole('dialog', { name: 'Start Session 2' }))

    await waitFor(() => expect(fact('Session')).toBe('Day 1 · Session 2'))
    expect(sent).toEqual([{ method: 'POST', address: '/api/mission/next-session', body: { keep_teams } }])
    expect(fact('Status')).toBe('Active')
    expect(screen.queryByRole('dialog')).toBeNull()
})

test('a session started on a later date is on the next day', async () => {
    // Arizona07's first session started on April 13, 2025. Its second starts in November 2026.
    pretendBackend([], { ...ARIZONA07, status: 'paused', asks_to_continue: false })
    await openMissionPanel()

    press('Start Session 2')
    press('Start with no teams', screen.getByRole('dialog'))

    await waitFor(() => expect(fact('Session')).toBe('Day 2 · Session 2'))
})

// A session still active when the app opens

test('a session still active when the app opens asks, and Continue carries on', async () => {
    const sent = pretendBackend([], bearCreek('active', true))
    render(<MissionProvider><App /></MissionProvider>)

    const box = await screen.findByRole('dialog', { name: 'Session 1 is still running' })
    press('Continue', box)

    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())
    expect(sent).toEqual([{ method: 'POST', address: '/api/mission/continue' }])
})

test('"End Session now" on that question ends the session', async () => {
    const sent = pretendBackend([], bearCreek('active', true))
    await openMissionPanel()

    press('End Session now', screen.getByRole('dialog'))

    await waitFor(() => expect(fact('Status')).toBe('Paused'))
    expect(sent).toEqual([{ method: 'POST', address: '/api/mission/end-session' }])
    expect(screen.queryByRole('dialog')).toBeNull()
})

// The time zone

test('changing the time zone saves it and every time on screen shifts', async () => {
    const sent = pretendBackend([], bearCreek('active'))
    await openMissionPanel()
    expect(fact('Started')).toBe('Nov 20, 2026, 8:00 am')

    fireEvent.change(screen.getByRole('combobox', { name: 'Time zone' }), { target: { value: 'America/New_York' } })

    await waitFor(() => expect(fact('Started')).toBe('Nov 20, 2026, 10:00 am'))
    expect(sent).toEqual([{ method: 'PATCH', address: '/api/mission', body: { time_zone: 'America/New_York' } }])
})

test('an ended mission shows its time zone and cannot change it', async () => {
    pretendBackend([], { ...ARIZONA07, asks_to_continue: false })
    await openMissionPanel()

    expect(screen.queryByRole('combobox', { name: 'Time zone' })).toBeNull()
    expect(fact('Time zone')).toBe('Arizona')
})

test('a mission whose time zone is not on the list still shows in its own zone', async () => {
    pretendBackend([], { ...bearCreek('active'), time_zone: 'Europe/Paris' })
    await openMissionPanel()

    expect((screen.getByRole('combobox', { name: 'Time zone' }) as HTMLSelectElement).value).toBe('Europe/Paris')
    expect(fact('Started')).toBe('Nov 20, 2026, 4:00 pm')
})

// Closing

test('Close Mission goes back to the list of missions', async () => {
    const sent = pretendBackend([ARIZONA07], { ...ARIZONA07, asks_to_continue: false })
    await openMissionPanel()

    press('Close Mission')

    expect(await screen.findByRole('button', { name: 'Arizona07 · Ended' })).toBeTruthy()
    expect(sent).toEqual([{ method: 'POST', address: '/api/mission/close' }])
    expect(screen.getByRole('button', { name: /^Mission/ }).textContent).toBe('Mission+ New')
})

test('a refused change is shown in the panel and nothing switches', async () => {
    pretendBackend([], bearCreek('planning'), { '/api/mission/start': 'Only a mission in planning can be started.' })
    await openMissionPanel()

    press('Start Mission')

    expect((await screen.findByRole('alert')).textContent).toBe('Only a mission in planning can be started.')
    expect(fact('Status')).toBe('Planning')
})

test('if the open mission cannot be read, the app still draws and the panel says so', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => jsonAnswer({}, 500)))
    await openMissionPanel()

    expect(screen.getByText('The open mission could not be read from the backend.')).toBeTruthy()
})
