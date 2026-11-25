import type { StyleSpecification } from 'maplibre-gl'
import { expect, test } from 'vitest'
import { hideGroups, keepAdded } from './styleChoices.ts'

// The backend's style, cut down to two layers.
const BASE: StyleSpecification = {
    version: 8,
    sources: { basemap: { type: 'vector', url: 'pmtiles://basemap' } },
    layers: [
        { id: 'roads', type: 'line', source: 'basemap', 'source-layer': 'roads' },
        { id: 'contours', type: 'line', source: 'basemap', 'source-layer': 'contours', metadata: { group: 'contours' } },
    ],
}

// What the map is drawing: the backend's style, and a rectangle a drawing tool added on top.
const DRAWING: StyleSpecification = {
    ...BASE,
    sources: { ...BASE.sources, 'td-polygon': { type: 'geojson', data: { type: 'FeatureCollection', features: [] } } },
    layers: [...BASE.layers, { id: 'td-polygon', type: 'fill', source: 'td-polygon' }],
}

test('what was added to the map is kept, on top, when a layer group is hidden', () => {
    const next = hideGroups(BASE, ['contours'])

    const kept = keepAdded(BASE, DRAWING, next)

    expect(kept.layers.map((layer) => layer.id)).toEqual(['roads', 'contours', 'td-polygon'])
    expect(Object.keys(kept.sources)).toEqual(['basemap', 'td-polygon'])
    // The change itself still goes through: the contours are hidden.
    expect(kept.layers[1].layout).toEqual({ visibility: 'none' })
})

test('with nothing added, the next style is used as it is', () => {
    const next = hideGroups(BASE, ['contours'])
    expect(keepAdded(BASE, BASE, next)).toEqual(next)
})

test('before the map has drawn any style, the next style is used as it is', () => {
    expect(keepAdded(BASE, undefined, BASE)).toEqual(BASE)
})
