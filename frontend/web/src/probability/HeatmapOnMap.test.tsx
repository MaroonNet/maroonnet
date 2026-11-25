import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import type { LayerChoice } from '../layers/missionLayers.ts'
import HeatmapOnMap from './HeatmapOnMap.tsx'
import { ProbabilityContext } from './probability.ts'
import { board, overlay } from './sample.ts'
import type { Overlay } from './probability.ts'

// The map library's two pieces for drawing, as boxes that print what they were given.
vi.mock('react-map-gl/maplibre', () => ({
    Source: ({ id, type, url, coordinates, children }: { id: string, type: string, url?: string, coordinates?: unknown, children: unknown }) => (
        <div data-testid="source" data-id={id} data-type={type} data-url={url} data-coordinates={JSON.stringify(coordinates)}>{children as never}</div>
    ),
    Layer: ({ id, type, beforeId, paint, layout }: { id: string, type: string, beforeId?: string, paint: unknown, layout: unknown }) => (
        <div data-testid="layer" data-id={id} data-type={type} data-before={beforeId}>{JSON.stringify(paint)} {JSON.stringify(layout)}</div>
    ),
}))

afterEach(cleanup)

function draw(newest: Overlay | null, layer: LayerChoice = { shown: true, opacity: 1 }) {
    render(<ProbabilityContext value={board(newest)}><HeatmapOnMap layer={layer} /></ProbabilityContext>)
}

const picture = () => screen.getAllByTestId('source').find((source) => source.dataset.type === 'image')
const layerOf = (id: string) => screen.getAllByTestId('layer').find((layer) => layer.dataset.id === id)!

test("the newest map is one picture pinned by its four corners", () => {
    const made = overlay('120000')
    draw(made)
    expect(picture()!.dataset.url).toBe('/api/spm/predictions/20261125-120000_hiker/overlay.png')
    expect(JSON.parse(picture()!.dataset.coordinates!)).toEqual(made.coordinates)
    expect(layerOf('heatmap-picture').dataset.type).toBe('raster')
})

test('the picture is drawn under everything else of the mission: just below a place kept for it', () => {
    draw(overlay('120000'))
    const layers = screen.getAllByTestId('layer').map((layer) => layer.dataset.id)
    expect(layers).toContain('heatmap-place')
    expect(layerOf('heatmap-picture').dataset.before).toBe('heatmap-place')
})

test('the picture is as strong as the Probability heatmap layer\'s opacity', () => {
    draw(overlay('120000'), { shown: true, opacity: 0.6 })
    expect(layerOf('heatmap-picture').textContent).toContain('"raster-opacity":0.6')
    expect(layerOf('heatmap-picture').textContent).toContain('"visibility":"visible"')
})

test('with the layer unticked the picture is not drawn', () => {
    draw(overlay('120000'), { shown: false, opacity: 1 })
    expect(layerOf('heatmap-picture').textContent).toContain('"visibility":"none"')
})

test('a mission with no map has no picture, and the place for one is still kept', () => {
    draw(null)
    expect(picture()).toBeUndefined()
    expect(layerOf('heatmap-place')).toBeTruthy()
})
