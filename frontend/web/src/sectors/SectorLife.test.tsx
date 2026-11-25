import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import { MissionContext, type MissionStatus } from '../mission/mission.ts'
import { PeopleContext } from '../people/people.ts'
import { SettingsContext } from '../settings/settings.ts'
import { arizona, GROUPS, PEOPLE, RADIOS } from '../teams/sample.ts'
import { held, NO_LIFE, sector } from './sample.ts'
import SectorCard from './SectorCard.tsx'
import { SectorsContext, type Sector, type SectorsBoard } from './sectors.ts'

// The card's buttons for the rest of a sector's life. The teams are the team tests' own:
// Group 1 is Radios 1 and 2 and holds S4, Group 2 is Radio 7, Group 3 has no teams.

afterEach(cleanup)

type Life = Partial<Pick<SectorsBoard, 'assign' | 'release' | 'markEntered' | 'complete'>>

function show(sectors: Sector[], id: number, life: Life = {}, status: MissionStatus = 'active') {
    const readPeople = vi.fn(async () => '')
    render(
        <SettingsContext value={{ settings: { units: 'imperial' }, loadFailed: false, change: async () => false }}>
            <MissionContext value={{ mission: arizona(status), loadFailed: false, run: async () => '' }}>
                <PeopleContext value={{ roster: [], people: PEOPLE, radios: RADIOS, groups: GROUPS, run: readPeople }}>
                    <SectorsContext value={{ sectors, loadedFor: 'az07', add: async () => '', changeShape: async () => '', remove: async () => '', ...NO_LIFE, ...life }}>
                        <SectorCard id={id} onClose={() => {}} onEdit={() => {}} />
                    </SectorsContext>
                </PeopleContext>
            </MissionContext>
        </SettingsContext>,
    )
    return readPeople
}

const fact = (label: string) => screen.getAllByText(label).find((element) => element.tagName === 'DT')?.nextSibling?.textContent
// The card's buttons, without its close button.
const buttons = () => screen.getAllByRole('button').map((button) => button.textContent).filter(Boolean)
const press = (name: string | RegExp) => fireEvent.click(screen.getByRole('button', { name }))

// Assign

test('a sector no group holds, drawn or partial, can be assigned', () => {
    show([sector(7, 'drawn'), sector(6, 'partial')], 7)
    expect(buttons()).toEqual(['Assign to Group'])
    cleanup()
    show([sector(6, 'partial')], 6)
    expect(buttons()).toEqual(['Assign to Group'])
})

test('Assign to Group lists the groups that have teams, each with the sector it holds', () => {
    show([sector(7, 'drawn')], 7)

    press('Assign to Group')

    expect(buttons()).toEqual(['Group 1 · holds S4', 'Group 2', 'Cancel'])  // Group 3 has no teams
})

test('picking a free group assigns the sector to it, and the groups are read again', async () => {
    const assign = vi.fn(async () => '')
    const readPeople = show([sector(7, 'drawn')], 7, { assign })

    press('Assign to Group')
    press('Group 2')

    expect(assign).toHaveBeenCalledWith(7, 2)
    await waitFor(() => expect(readPeople).toHaveBeenCalledOnce())
    expect(buttons()).not.toContain('Cancel')  // the list is gone
})

test('picking a group that holds a sector asks first, saying the old one is released, not completed', () => {
    const assign = vi.fn(async () => '')
    show([sector(7, 'drawn')], 7, { assign })
    press('Assign to Group')

    press(/^Group 1/)

    const box = screen.getByRole('dialog', { name: 'Give S7 to Group 1?' })
    expect(box.textContent).toContain('Group 1 holds S4. S4 will be released, not completed.')
    expect(assign).not.toHaveBeenCalled()

    fireEvent.click(within(box).getByRole('button', { name: 'Assign' }))
    expect(assign).toHaveBeenCalledWith(7, 1)
})

test('Cancel in the list goes back to the card with nothing assigned', () => {
    const assign = vi.fn(async () => '')
    show([sector(7, 'drawn')], 7, { assign })
    press('Assign to Group')

    press('Cancel')

    expect(buttons()).toEqual(['Assign to Group'])
    expect(assign).not.toHaveBeenCalled()
})

test('with no group that has a team, the list says where groups are made', () => {
    render(
        <MissionContext value={{ mission: arizona(), loadFailed: false, run: async () => '' }}>
            <SectorsContext value={{ sectors: [sector(7, 'drawn')], loadedFor: 'az07', add: async () => '', changeShape: async () => '', remove: async () => '', ...NO_LIFE }}>
                <SectorCard id={7} onClose={() => {}} onEdit={() => {}} />
            </SectorsContext>
        </MissionContext>,
    )
    press('Assign to Group')
    expect(screen.getByText('No group has a team yet. Groups are made in Groups & Teams.')).toBeTruthy()
})

test('a refused assignment is said on the card', async () => {
    show([sector(7, 'drawn')], 7, { assign: async () => 'Group 2 has no teams, so it cannot be given a sector.' })
    press('Assign to Group')
    press('Group 2')
    expect((await screen.findByRole('alert')).textContent).toBe('Group 2 has no teams, so it cannot be given a sector.')
})

// A sector a group holds

test("an assigned sector's card: Assigned, its group, when it was given, and its four buttons", () => {
    show([held(4, 'partial', 1)], 4)
    expect(screen.getByText('Assigned', { selector: 'p' })).toBeTruthy()
    expect(fact('Group')).toBe('Group 1')
    expect(fact('Assigned')).toBe('8:50 pm')
    expect(buttons()).toEqual(['Mark Entered', 'Mark Completed', 'Release', 'Message'])
    expect(screen.getByRole('button', { name: 'Message' }).getAttribute('title')).toBe('Not available yet')
})

test('a searching sector says when a team entered, and has no Mark Entered', () => {
    show([held(4, 'searching', 1, { entered_time: '2025-04-14T04:10:00Z' })], 4)
    expect(screen.getByText('Searching', { selector: 'p' })).toBeTruthy()
    expect(fact('Entered')).toBe('9:10 pm')
    expect(buttons()).toEqual(['Mark Completed', 'Release', 'Message'])
})

test('while the mission is in planning a held sector can be released, not entered or completed', () => {
    show([held(4, 'drawn', 1)], 4, {}, 'planning')
    expect(buttons()).toEqual(['Release', 'Message'])
    expect(screen.getByText('Start the mission to mark it entered or completed.')).toBeTruthy()
})

test('in a paused or ended session the card has no buttons for assigning', () => {
    show([held(4, 'searching', 1), sector(7, 'drawn')], 4, {}, 'paused')
    expect(buttons()).toEqual([])
    cleanup()
    show([sector(7, 'drawn')], 7, {}, 'ended')
    expect(buttons()).toEqual([])
})

test('Release takes the group off the sector', async () => {
    const release = vi.fn(async () => '')
    const readPeople = show([held(4, 'searching', 1)], 4, { release })

    press('Release')

    expect(release).toHaveBeenCalledWith(4)
    await waitFor(() => expect(readPeople).toHaveBeenCalledOnce())
})

// Mark Entered

test('with one team in the group, Mark Entered is one press', () => {
    const markEntered = vi.fn(async () => '')
    show([held(5, 'drawn', 2)], 5, { markEntered })  // Group 2 is Radio 7 only

    press('Mark Entered')

    expect(markEntered).toHaveBeenCalledWith(5, 7)
})

test('with two teams in the group, Mark Entered asks which team entered', () => {
    const markEntered = vi.fn(async () => '')
    show([held(4, 'drawn', 1)], 4, { markEntered })

    press('Mark Entered')

    expect(screen.getByText('Which team entered S4?')).toBeTruthy()
    expect(buttons()).toEqual(['Radio 1Marcus Ibarra, Tessa Lindqvist', 'Radio 2Priya Raman', 'Cancel'])
    expect(markEntered).not.toHaveBeenCalled()

    press(/^Radio 2/)
    expect(markEntered).toHaveBeenCalledWith(4, 2)
})

// Mark Completed

test('Mark Completed asks first, with no POD box; Cancel completes nothing', () => {
    const complete = vi.fn(async () => '')
    show([held(4, 'searching', 1)], 4, { complete })

    press('Mark Completed')

    const box = screen.getByRole('dialog', { name: 'Mark S4 completed?' })
    expect(box.textContent).toContain('Group 1 is taken off it. A completed sector is final and cannot be reopened.')
    expect(within(box).queryByRole('textbox')).toBeNull()
    expect(within(box).queryByRole('spinbutton')).toBeNull()

    fireEvent.click(within(box).getByRole('button', { name: 'Cancel' }))
    expect(complete).not.toHaveBeenCalled()
})

test('Mark Completed in the box completes the sector', () => {
    const complete = vi.fn(async () => '')
    show([held(4, 'drawn', 1)], 4, { complete })

    press('Mark Completed')
    fireEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Mark Completed' }))

    expect(complete).toHaveBeenCalledWith(4)
})

// What is kept of a sector's past

test('a completed sector says which group completed it, and offers nothing more', () => {
    show([sector(1, 'completed', { completed_by: 1 })], 1)
    expect(fact('Completed')).toBe('1:21 am')
    expect(fact('Completed by')).toBe('Group 1')
    expect(buttons()).toEqual([])
})

test("the card shows a sector's saved sends as one line, and nothing for a sector never sent", () => {
    const sends = [1, 2].map((radio_id) => ({ radio_id, sent_time: '2025-04-14T03:50:55Z', ack_time: '2025-04-14T03:51:08Z' }))
    show([sector(1, 'completed', { sends }), sector(7, 'drawn')], 1)
    expect(screen.getByText('Sent to Radios 1, 2 · all acknowledged')).toBeTruthy()
    cleanup()
    show([sector(7, 'drawn')], 7)
    expect(screen.queryByText(/^Sent to/)).toBeNull()
})
