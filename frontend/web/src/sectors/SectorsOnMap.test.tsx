import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import { STRIPES, stripesImage } from './looks.ts'
import { SectorsContext, type Sector } from './sectors.ts'
import SectorsOnMap from './SectorsOnMap.tsx'

// The map library's two pieces for drawing a shape, as boxes that print what they were given.
vi.mock('react-map-gl/maplibre', () => ({
    Source: ({ data, children }: { data: unknown, children: unknown }) => <div data-testid="source">{JSON.stringify(data)}{children as never}</div>,
    Layer: ({ id, paint, filter }: { id: string, paint: unknown, filter: unknown }) => (
        <div data-testid="layer">{id} {JSON.stringify(paint)} {JSON.stringify(filter)}</div>
    ),
}))

// A pretend map that records the pictures it was given and the events listened for. A
// listener for one layer is kept under "click sectors-hit".
type Listener = (event: { id: string, features?: { properties: { id: number } }[] }) => void
const pretend = vi.hoisted(() => ({
    map: {
        images: new Set<string>(),
        hasImage(name: string) { return this.images.has(name) },
        addImage: (() => {}) as (name: string, image: unknown, options: unknown) => void,
        listeners: {} as Record<string, Listener>,
        on(type: string, layerOrListener: string | Listener, listener?: Listener) {
            if (typeof layerOrListener === 'string') this.listeners[`${type} ${layerOrListener}`] = listener!
            else this.listeners[type] = layerOrListener
        },
        off(type: string, layerOrListener: string | Listener) {
            delete this.listeners[typeof layerOrListener === 'string' ? `${type} ${layerOrListener}` : type]
        },
        getCanvas: () => ({ style: { cursor: '' } }),
    },
}))
vi.mock('../map/missionMap.ts', () => ({ useMissionMap: () => pretend.map }))

afterEach(() => {
    cleanup()
    pretend.map.images.clear()
    pretend.map.listeners = {}
})

function sector(id: number, status: Sector['status'], group_id: number | null = null): Sector {
    return {
        id, name: `S${id}`, status, group_id, can_edit: false,
        corners: [{ lat: 31.5, lon: -110.7 }, { lat: 31.51, lon: -110.7 }, { lat: 31.51, lon: -110.69 }],
        created_time: '2025-04-14T03:35:00Z', completed_time: null,
    }
}

function draw(sectors: Sector[], selected: number | null = null, onPick?: (id: number) => void) {
    const addImage = vi.fn((name: string) => { pretend.map.images.add(name) })
    pretend.map.addImage = addImage
    render(
        <SectorsContext value={{ sectors, loadedFor: 'az07', add: async () => '' }}>
            <SectorsOnMap selected={selected} onPick={onPick} />
        </SectorsContext>,
    )
    const shapes = JSON.parse(screen.getByTestId('source').firstChild!.textContent!)
    return { shapes, addImage }
}

type Shape = { properties: { look: string }, geometry: { type: string, coordinates: unknown } }
const polygons = (shapes: { features: Shape[] }) => shapes.features.filter((f) => f.geometry.type === 'Polygon')

test("each sector is drawn with its status's look: green completed, striped partial, red drawn", () => {
    const { shapes } = draw([sector(1, 'completed'), sector(4, 'partial'), sector(7, 'drawn')])
    expect(polygons(shapes).map((f) => f.properties)).toEqual([
        { id: 1, name: 'S1', look: 'completed' },
        { id: 4, name: 'S4', look: 'partial' },
        { id: 7, name: 'S7', look: 'drawn' },
    ])
})

test('until assigning is built (D7), an assigned or searching sector has the drawn look', () => {
    const { shapes } = draw([sector(2, 'drawn', 3), sector(3, 'searching', 1)])
    expect(polygons(shapes).map((f) => f.properties.look)).toEqual(['drawn', 'drawn'])
})

test("each sector has one label point, at the middle of its ground, so a sector cut by the map's tiles is labeled once", () => {
    const { shapes } = draw([sector(7, 'drawn')])
    const points = shapes.features.filter((f: Shape) => f.geometry.type === 'Point')
    expect(points).toHaveLength(1)
    expect(points[0].properties).toEqual({ id: 7, name: 'S7', look: 'drawn' })
    expect(layer('sectors-label')).toContain('["==",["geometry-type"],"Point"]')
})

test('a sector is drawn round its corners and back to the first, longitude first', () => {
    const { shapes } = draw([sector(7, 'drawn')])
    expect(polygons(shapes)[0].geometry).toEqual({
        type: 'Polygon',
        coordinates: [[[-110.7, 31.5], [-110.7, 31.51], [-110.69, 31.51], [-110.7, 31.5]]],
    })
})

test('the outline is red, orange or green by look, and the stripes fill only partial sectors', () => {
    draw([sector(4, 'partial')])
    const layers = screen.getAllByTestId('layer').map((layer) => layer.textContent!)
    const outline = layers.find((text) => text.startsWith('sectors-line'))!
    expect(outline).toContain('#c9302d')  // red
    expect(outline).toContain('#e57600')  // orange
    expect(outline).toContain('#218a45')  // green
    const stripes = layers.find((text) => text.startsWith('sectors-stripes'))!
    expect(stripes).toContain(`"fill-pattern":"${STRIPES}"`)
    expect(stripes).toContain('"partial"')
})

const layer = (id: string) => screen.getAllByTestId('layer').map((l) => l.textContent!).find((text) => text.startsWith(`${id} `))!

test('each sector is labeled with its name, in its look\'s color', () => {
    draw([sector(7, 'drawn')])
    const labels = layer('sectors-label')
    expect(labels).toContain('#c9302d')
})

test('the selected sector is drawn with a stronger outline', () => {
    draw([sector(1, 'completed'), sector(7, 'drawn')], 7)
    expect(layer('sectors-line')).toContain('["==",["get","id"],7]')
})

test('while picking is on, a click on a sector picks it', () => {
    const onPick = vi.fn()
    draw([sector(7, 'drawn')], null, onPick)

    pretend.map.listeners['click sectors-hit']({ id: '', features: [{ properties: { id: 7 } }] })

    expect(onPick).toHaveBeenCalledWith(7)
})

test('while a drawing tool is in use, a click on a sector picks nothing', () => {
    draw([sector(7, 'drawn')])
    expect(pretend.map.listeners['click sectors-hit']).toBeUndefined()
})

test('the stripe picture is given to the map, and given again when the map asks for it', () => {
    const { addImage } = draw([sector(4, 'partial')])
    expect(addImage).toHaveBeenCalledOnce()
    expect(addImage.mock.calls[0][0]).toBe(STRIPES)

    // A new map style drops pictures that were added; the map then asks for the missing one.
    pretend.map.images.clear()
    pretend.map.listeners.styleimagemissing({ id: STRIPES })
    expect(addImage).toHaveBeenCalledTimes(2)
})

test('the stripe picture repeats with no seam: a stripe leaving its right edge goes on at its left', () => {
    const { width, height, data } = stripesImage()
    const alpha = (x: number, y: number) => data[(y * width + x) * 4 + 3]
    // The stripes rise to the right, so the next pixel along one is a step right and a step up.
    for (let y = 0; y < height; y++) expect(alpha(width - 1, y) > 0).toBe(alpha(0, (y - 1 + height) % height) > 0)
    expect([...data].some((value, i) => i % 4 === 3 && value === 0)).toBe(true)  // clear between the stripes
})
