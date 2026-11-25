import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import { MissionContext, type OpenMission } from '../mission/mission.ts'
import { PeopleContext } from '../people/people.ts'
import { arizona, GROUPS, PEOPLE, RADIOS } from './sample.ts'
import type { Group, Radio } from './teams.ts'
import TeamsPanel from './TeamsPanel.tsx'

afterEach(() => {
    cleanup()
    vi.unstubAllGlobals()
})

// Stands in for the backend: every request is noted and answered.
function pretendBackend(refuse: Record<string, string> = {}) {
    const sent: { method: string, address: string, body?: unknown }[] = []
    vi.stubGlobal('fetch', vi.fn(async (address: string, request?: RequestInit) => {
        const method = request?.method ?? 'GET'
        sent.push({ method, address, body: request?.body ? JSON.parse(request.body as string) : undefined })
        const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { 'content-type': 'application/json' } })
        if (refuse[address]) return json({ detail: refuse[address] }, 409)
        return json({})
    }))
    return sent
}

function show(mission: OpenMission | null = arizona(), radios: Radio[] = RADIOS, groups: Group[] = GROUPS, onPick = vi.fn()) {
    const run = async (request: Promise<unknown>) => request.then(() => '', (error: Error) => error.message)
    render(
        <MissionContext value={{ mission, loadFailed: false, run: async () => '' }}>
            <PeopleContext value={{ roster: [], people: mission ? PEOPLE : [], radios: mission ? radios : [], groups: mission ? groups : [], run }}>
                <TeamsPanel selected={1} onPick={onPick} />
            </PeopleContext>
        </MissionContext>,
    )
    return onPick
}

const rows = (name: string) => within(screen.getByRole('list', { name })).getAllByRole('listitem').map((row) => row.textContent)
const press = (name: string | RegExp) => fireEvent.click(screen.getByRole('button', { name }))
const tick = (name: string) => fireEvent.click(screen.getByRole('checkbox', { name }))
const ticked = () => screen.getAllByRole('checkbox').filter((box) => (box as HTMLInputElement).checked).map((box) => box.getAttribute('aria-label'))

// The list.

test('the panel lists each group with its teams, then the teams with no group', () => {
    show()
    expect(rows('Group 1')).toEqual([
        'Radio 1Marcus Ibarra, Tessa LindqvistLast position 4:19 amEdit', 'Radio 2Priya RamanLast position 4:18 amEdit'])
    expect(rows('Group 2')).toEqual(['Radio 7Ana MoralesLast position 4:17 amEdit'])
    expect(rows('No group')).toEqual(['Radio 4Diego AlasNo position yetEdit'])
    // A group with no teams stays listed.
    expect(screen.getByRole('button', { name: 'Group 3 · no teams' })).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Group 1 · S4' })).toBeTruthy()
})

test('only searcher radios with someone on them are teams', () => {
    show()
    expect(screen.queryByText('Radio 5')).toBeNull()  // nobody on it
    expect(screen.queryByText('Radio 6')).toBeNull()  // the relay
    expect(screen.queryByText('Radio 8')).toBeNull()  // the command post radio
})

test('pressing a team selects it, and the selected team is marked', () => {
    const onPick = show()
    press('Radio 7')
    expect(onPick).toHaveBeenCalledWith(7)
    expect(screen.getByRole('button', { name: 'Radio 1' }).getAttribute('aria-current')).toBe('true')
})

test('with no mission open the panel says so', () => {
    show(null)
    expect(screen.getByText('No mission is open.')).toBeTruthy()
    expect(screen.queryByRole('button', { name: 'Add Team' })).toBeNull()
})

test('with no teams the panel says how to make one, and Add Group waits for a team', () => {
    show(arizona('planning'), RADIOS.map((radio) => ({ ...radio, people: [], group_id: null })), [])
    expect(screen.getByText('No teams yet.')).toBeTruthy()
    expect((screen.getByRole('button', { name: 'Add Group' }) as HTMLButtonElement).disabled).toBe(true)
    expect((screen.getByRole('button', { name: 'Add Team' }) as HTMLButtonElement).disabled).toBe(false)
})

test('a session that has ended shows its teams and nothing to change them with', () => {
    show(arizona('ended'))
    expect(rows('Group 2')).toEqual(['Radio 7Ana MoralesLast position 4:17 am'])
    expect(screen.queryByRole('button', { name: 'Add Team' })).toBeNull()
    expect(screen.queryByRole('button', { name: 'Add Group' })).toBeNull()
})

// The team form.

test('Add Team offers the radios with nobody, the groups, and the checked-in people with no radio', () => {
    show()
    press('Add Team')
    const options = (name: string) => within(screen.getByRole('combobox', { name })).getAllByRole('option').map((option) => option.textContent)
    expect(options('Radio')).toEqual(['Radio 5'])
    expect(options('Group')).toEqual(['No group', 'Group 1', 'Group 2', 'Group 3'])
    expect(screen.getAllByRole('checkbox').map((box) => box.getAttribute('aria-label'))).toEqual(['Naomi Feld', 'Searcher #1'])
})

test('a new team is saved with its radio, its searchers and its group', async () => {
    const sent = pretendBackend()
    show()
    press('Add Team')
    expect((screen.getByRole('button', { name: 'Save Team' }) as HTMLButtonElement).disabled).toBe(true)  // nobody ticked
    tick('Naomi Feld')
    fireEvent.change(screen.getByRole('combobox', { name: 'Group' }), { target: { value: '2' } })
    press('Save Team')
    await waitFor(() => expect(sent).toEqual([
        { method: 'POST', address: '/api/mission/teams', body: { radio_id: 5, searcher_ids: [9], group_id: 2 } }]))
    await screen.findByRole('button', { name: 'Add Team' })  // back at the list
})

test('with no radio free the form says so', () => {
    show(arizona(), RADIOS.filter((radio) => radio.id !== 5))
    press('Add Team')
    expect(screen.getByText('Every searcher radio already has someone on it.')).toBeTruthy()
})

test('Edit Team shows the team as it is, with its radio fixed', () => {
    show()
    press('Edit Radio 1')
    expect(screen.queryByRole('combobox', { name: 'Radio' })).toBeNull()
    expect(screen.getByRole('heading', { name: 'Edit Radio 1' })).toBeTruthy()
    expect((screen.getByRole('combobox', { name: 'Group' }) as HTMLSelectElement).value).toBe('1')
    expect(screen.getAllByRole('checkbox').map((box) => box.getAttribute('aria-label'))).toEqual([
        'Marcus Ibarra', 'Tessa Lindqvist', 'Naomi Feld', 'Searcher #1'])
    expect(ticked()).toEqual(['Marcus Ibarra', 'Tessa Lindqvist'])
})

test('an edited team is saved with who is ticked and the group picked', async () => {
    const sent = pretendBackend()
    show()
    press('Edit Radio 1')
    tick('Tessa Lindqvist')
    tick('Naomi Feld')
    press('Save Team')
    await waitFor(() => expect(sent).toEqual([
        { method: 'PUT', address: '/api/mission/teams/1', body: { searcher_ids: [1, 9], group_id: 1 } }]))
})

test('taking everyone off a radio warns first', async () => {
    const sent = pretendBackend()
    show()
    press('Edit Radio 2')
    tick('Priya Raman')
    press('Save Team')
    const box = within(screen.getByRole('dialog', { name: 'Take everyone off Radio 2?' }))
    expect(box.getByText('Radio 2 will have nobody on it, and it leaves Group 1.')).toBeTruthy()
    expect(sent).toEqual([])
    fireEvent.click(box.getByRole('button', { name: 'Take Everyone Off' }))
    await waitFor(() => expect(sent).toEqual([
        { method: 'PUT', address: '/api/mission/teams/2', body: { searcher_ids: [], group_id: null } }]))
})

test('moving the only team out of a group warns that the group will have no teams', async () => {
    const sent = pretendBackend()
    show()
    press('Edit Radio 7')
    fireEvent.change(screen.getByRole('combobox', { name: 'Group' }), { target: { value: '' } })
    press('Save Team')
    const box = within(screen.getByRole('dialog', { name: 'Leave Group 2 with no teams?' }))
    expect(box.getByText('Radio 7 is the only team in Group 2. Group 2 stays listed with no teams, and can be given teams again.')).toBeTruthy()
    fireEvent.click(box.getByRole('button', { name: 'Cancel' }))
    expect(sent).toEqual([])
    expect(screen.queryByRole('dialog')).toBeNull()

    press('Save Team')
    fireEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Move Team' }))
    await waitFor(() => expect(sent).toEqual([
        { method: 'PUT', address: '/api/mission/teams/7', body: { searcher_ids: [18], group_id: null } }]))
})

test('a team the backend refuses shows the reason and keeps the form', async () => {
    pretendBackend({ '/api/mission/teams': 'Naomi Feld already carries Radio 3.' })
    show()
    press('Add Team')
    tick('Naomi Feld')
    press('Save Team')
    expect((await screen.findByRole('alert')).textContent).toBe('Naomi Feld already carries Radio 3.')
    expect(screen.getByRole('button', { name: 'Save Team' })).toBeTruthy()
})

// The group form and the group view.

test('Add Group lists every team with the group it is in now', () => {
    show()
    press('Add Group')
    expect(rows('Teams')).toEqual([
        'Radio 1Marcus Ibarra, Tessa LindqvistGroup 1', 'Radio 2Priya RamanGroup 1', 'Radio 4Diego AlasNo group', 'Radio 7Ana MoralesGroup 2'])
    expect((screen.getByRole('button', { name: 'Save Group' }) as HTMLButtonElement).disabled).toBe(true)  // no team ticked
})

test('a new group is saved with its teams', async () => {
    const sent = pretendBackend()
    show()
    press('Add Group')
    tick('Radio 4')
    tick('Radio 2')
    press('Save Group')
    await waitFor(() => expect(sent).toEqual([
        { method: 'POST', address: '/api/mission/groups', body: { radio_ids: [2, 4] } }]))
    await screen.findByRole('button', { name: 'Add Team' })
})

test('taking every team of another group warns first', async () => {
    const sent = pretendBackend()
    show()
    press('Add Group')
    tick('Radio 7')
    press('Save Group')
    const box = within(screen.getByRole('dialog', { name: 'Leave Group 2 with no teams?' }))
    expect(box.getByText('Group 2 stays listed with no teams, and can be given teams again.')).toBeTruthy()
    expect(sent).toEqual([])
    fireEvent.click(box.getByRole('button', { name: 'Save Group' }))
    await waitFor(() => expect(sent).toHaveLength(1))
})

test('pressing a group shows its sector and teams, with Edit', () => {
    show()
    press('Group 1 · S4')
    expect(screen.getByRole('heading', { name: 'Group 1' })).toBeTruthy()
    expect(screen.getByText('Holds sector S4')).toBeTruthy()
    expect(rows('Group 1')).toHaveLength(2)
    press('‹ Groups & Teams')
    expect(screen.getByRole('button', { name: 'Add Team' })).toBeTruthy()
})

test('editing a group sets which teams are in it', async () => {
    const sent = pretendBackend()
    show()
    press('Group 1 · S4')
    press('Edit Group')
    expect(ticked()).toEqual(['Radio 1', 'Radio 2'])
    tick('Radio 2')
    tick('Radio 4')
    press('Save Group')
    await waitFor(() => expect(sent).toEqual([
        { method: 'PUT', address: '/api/mission/groups/1', body: { radio_ids: [1, 4] } }]))
})

test('a group with no teams says so, and can be given teams', () => {
    show()
    press('Group 3 · no teams')
    expect(screen.getByText('No teams. Edit the group to give it teams.')).toBeTruthy()
    expect(screen.getByText('Holds no sector')).toBeTruthy()
    press('Edit Group')
    expect(ticked()).toEqual([])
    expect((screen.getByRole('button', { name: 'Save Group' }) as HTMLButtonElement).disabled).toBe(true)  // nothing changed
})
