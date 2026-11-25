import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, expect, test } from 'vitest'
import TeamMarker, { TeamPill } from './TeamMarker.tsx'
import { groupColor, NO_GROUP_COLOR } from './teamWords.ts'
import type { Radio } from './teams.ts'

afterEach(cleanup)

// A team of one searcher on this radio, in this group.
function team(id: number, group_id: number | null): Radio {
    return {
        id, node_num: 100 + id, kind: 'searcher', group_id,
        people: [{ id: 50 + id, name: `Searcher ${id}`, placeholder: false }],
        last_position: { time: '2025-04-14T11:19:00Z', lat: 31.4, lon: -110.6, elevation: 1500 },
    }
}

// A color as the pretend browser writes it back.
function written(color: string): string {
    const probe = document.createElement('span')
    probe.style.background = color
    return probe.style.background
}

test("on the map a team is a dot 14 across in its group's color, grey for none, with a white border", () => {
    const { container, rerender } = render(<TeamMarker radio={team(3, 2)} />)
    const dot = container.firstElementChild as HTMLElement
    expect(dot.className).toContain('size-3.5')
    expect(dot.className).toContain('border-field')
    expect(dot.style.background).toBe(written(groupColor(2)))
    expect(dot.textContent).toBe('')
    rerender(<TeamMarker radio={team(4, null)} />)
    expect((container.firstElementChild as HTMLElement).style.background).toBe(written(NO_GROUP_COLOR))
})

test("a selected team's dot has a ring", () => {
    const { container, rerender } = render(<TeamMarker radio={team(3, 2)} />)
    expect(container.firstElementChild!.className).not.toContain('outline-ink')
    rerender(<TeamMarker radio={team(3, 2)} ringed />)
    expect(container.firstElementChild!.className).toContain('outline-ink')
})

test("the pill names the group on the group's color, then the radio: G2 R3", () => {
    const { container } = render(<TeamPill radio={team(3, 2)} />)
    expect(container.textContent).toBe('G2R3')
    expect(screen.getByText('G2').style.background).toBe(written(groupColor(2)))
    expect(screen.getByText('R3').className).toContain('bg-field')
    expect(container.firstElementChild!.className).toContain('border-field')
})

test('a team in no group has a one-part pill: R4', () => {
    const { container } = render(<TeamPill radio={team(4, null)} />)
    expect(container.textContent).toBe('R4')
})
