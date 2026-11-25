import { cleanup, render } from '@testing-library/react'
import { afterEach, expect, test } from 'vitest'
import KindMarker from './KindMarker.tsx'
import { kindOf } from './kinds.ts'

afterEach(cleanup)

const WHITE = '#fffdf6'  // --color-field in index.css

test("on the map a waypoint is a pin: a head 24 across with a short point below, in its kind's color with a white border, and its icon in the head", () => {
    const { container } = render(<KindMarker kind="evidence" pin />)
    const outline = container.querySelector('[data-outline]')!
    expect(outline.getAttribute('width')).toBe('24')
    expect(outline.getAttribute('height')).toBe('31')
    const shape = outline.querySelector('path')!
    expect(shape.getAttribute('fill')).toBe(kindOf('evidence').color)
    expect(shape.getAttribute('stroke')).toBe(WHITE)
    expect(container.querySelector('.tabler-icon-zoom-exclamation')!.getAttribute('width')).toBe('14')
})

test('a selected pin has a ring around its head', () => {
    const { container, rerender } = render(<KindMarker kind="evidence" pin />)
    expect(container.querySelector('.outline-ink')).toBeNull()
    rerender(<KindMarker kind="evidence" pin ringed />)
    expect(container.querySelector('.outline-ink')!.className).toContain('rounded-full')
})

test('in a list or on a card a waypoint is a circle with a white border, at the size it had', () => {
    const { container, rerender } = render(<KindMarker kind="evidence" small />)
    expect(container.querySelector('[data-outline]')).toBeNull()
    const circle = container.firstElementChild!
    expect(circle.className).toContain('rounded-full')
    expect(circle.className).toContain('border-field')
    expect(circle.className).toContain('size-5.5')
    rerender(<KindMarker kind="evidence" />)
    expect(container.firstElementChild!.className).toContain('border-field')
    expect(container.firstElementChild!.className).toContain('size-7.5')
})
