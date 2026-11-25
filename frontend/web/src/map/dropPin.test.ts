import { expect, test, vi } from 'vitest'
import { dropPin } from './dropPin.ts'

// The map library's marker needs a real map. This stand-in keeps what it was made with.
const made = vi.hoisted(() => ({ options: null as unknown }))
vi.mock('maplibre-gl', () => ({
    Marker: class {
        constructor(options: unknown) { made.options = options }
        on() { return this }
        setLngLat() { return this }
        addTo() { return this }
        remove() { return this }
    },
}))

test("the pin's point is on the place: the pin hangs from its bottom, and can be dragged", () => {
    const map = { on() {}, off() {}, getCanvas: () => document.createElement('canvas') }
    dropPin(map as never, document.createElement('div'), { move() {} })
    expect(made.options).toMatchObject({ anchor: 'bottom', draggable: true })
})
