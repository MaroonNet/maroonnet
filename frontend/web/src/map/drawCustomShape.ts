import type { Feature, FeatureCollection } from 'geojson'
import type { GeoJSONSource, Map as MapLibreMap, MapMouseEvent } from 'maplibre-gl'
import { onOrInside, type Bounds, type Position } from './geo.ts'
import { addCorner, closeShape, EMPTY_DRAFT, redoCorner, undoCorner, type Refusal, type ShapeDraft } from './shapeDraft.ts'

// A custom shape being clicked out on the map.
export type CustomShapeDrawing = {
    undo: () => void      // takes the last corner away
    redo: () => void      // puts back the corner last taken away
    close: () => void     // closes the shape, as Enter does
    discard: () => void   // takes every corner away, ready to start again
    stop: () => void      // ends the drawing and takes its lines off the map
}

// The shape so far, after each click, Undo or Redo.
export type DraftFacts = {
    count: number                                // corners placed
    canUndo: boolean
    canRedo: boolean
    refused: Refusal | 'too-few' | null          // why the last click or close was not taken
}

type Listeners = {
    draft: (facts: DraftFacts) => void
    finish: (corners: Position[]) => void        // the shape was closed
}

const RED = '#c9302d'  // a drawn sector's red (SECTOR_COLORS in sectors/looks.ts)
const SOURCE = 'sector-draft'
const LAYERS = ['sector-draft-line', 'sector-draft-corners']
// A click this many pixels or nearer to the first corner, or to the last (the second click
// of a double-click), closes the shape.
const CLOSE_PIXELS = 10

// Lets the user click out a sector's corners one at a time, inside the search area. The
// rules for each click are in shapeDraft.ts. The shape so far is drawn as a dashed line,
// with a line on to the pointer, and a dot at each corner. A click on the first corner, a
// double-click, or close() closes it.
export function drawCustomShape(map: MapLibreMap, area: Bounds, on: Listeners): CustomShapeDrawing {
    let draft: ShapeDraft = EMPTY_DRAFT
    let pointer: Position | null = null   // where the next corner would go
    let closed = false                    // the shape is closed and handed on; clicks are ignored

    function show() {
        const source = map.getSource(SOURCE) as GeoJSONSource | undefined
        source?.setData(draftShapes(closed ? [] : draft.corners, closed ? null : pointer))
    }

    function report(refused: DraftFacts['refused'] = null) {
        on.draft({ count: draft.corners.length, canUndo: draft.corners.length > 0, canRedo: draft.undone.length > 0, refused })
        show()
    }

    // Whether the click was on a corner: within CLOSE_PIXELS of it on the screen.
    function onCorner(event: MapMouseEvent, corner: Position | undefined): boolean {
        if (!corner) return false
        const spot = map.project([corner.lon, corner.lat])
        return Math.hypot(spot.x - event.point.x, spot.y - event.point.y) <= CLOSE_PIXELS
    }

    function onClick(event: MapMouseEvent) {
        if (closed) return
        const first = draft.corners[0], last = draft.corners.at(-1)
        if (draft.corners.length >= 3 && (onCorner(event, first) || onCorner(event, last))) {
            close()
            return
        }
        if (onCorner(event, last)) return  // a second click on the same spot, too early to close
        const added = addCorner(draft, { lat: event.lngLat.lat, lon: event.lngLat.lng }, area)
        draft = added.draft
        report(added.refused)
    }

    function onMove(event: MapMouseEvent) {
        pointer = onOrInside({ lat: event.lngLat.lat, lon: event.lngLat.lng }, area)
        show()
    }

    function close() {
        if (closed) return
        const result = closeShape(draft)
        if ('refused' in result) {
            report(result.refused)
            return
        }
        closed = true
        show()  // the dashed line goes; the closed shape is drawn by whoever takes it on
        on.finish(result.corners)
    }

    // The map's style must have loaded before a source can be added. If it has not, the
    // drawing starts when the map next comes to rest ("idle").
    let started = false, stopped = false
    function start() {
        if (stopped) return
        started = true
        map.addSource(SOURCE, { type: 'geojson', data: draftShapes([], null) })
        map.addLayer({
            id: LAYERS[0], type: 'line', source: SOURCE,
            paint: { 'line-color': RED, 'line-width': 2, 'line-dasharray': [2, 1.5] },
        })
        map.addLayer({
            id: LAYERS[1], type: 'circle', source: SOURCE, filter: ['==', ['geometry-type'], 'Point'],
            paint: {
                // The first corner is larger once the shape can be closed on it.
                'circle-radius': ['case', ['get', 'closes'], 6, 4],
                'circle-color': '#ffffff', 'circle-stroke-color': RED, 'circle-stroke-width': 2,
            },
        })
        map.on('click', onClick)
        map.on('mousemove', onMove)
        map.getCanvas().style.cursor = 'crosshair'
        map.doubleClickZoom.disable()  // a double-click closes the shape, and does not zoom
    }
    if (map.isStyleLoaded()) start()
    else map.once('idle', start)

    return {
        undo() {
            if (closed) return
            draft = undoCorner(draft)
            report()
        },
        redo() {
            if (closed) return
            draft = redoCorner(draft)
            report()
        },
        close,
        discard() {
            draft = EMPTY_DRAFT
            closed = false
            report()
        },
        stop() {
            stopped = true
            if (!started) return
            map.off('click', onClick)
            map.off('mousemove', onMove)
            map.getCanvas().style.cursor = ''
            map.doubleClickZoom.enable()
            for (const layer of LAYERS) if (map.getLayer(layer)) map.removeLayer(layer)
            if (map.getSource(SOURCE)) map.removeSource(SOURCE)
        },
    }
}

// The shape so far as the map draws it: one line through the corners and on to the
// pointer, and a dot for each corner. The map takes longitude before latitude.
function draftShapes(corners: Position[], pointer: Position | null): FeatureCollection {
    const path = [...corners, ...(pointer && corners.length ? [pointer] : [])].map(({ lat, lon }) => [lon, lat])
    const features: Feature[] = corners.map((corner, i) => ({
        type: 'Feature',
        properties: { closes: i === 0 && corners.length >= 3 },
        geometry: { type: 'Point', coordinates: [corner.lon, corner.lat] },
    }))
    if (path.length >= 2) features.push({ type: 'Feature', properties: {}, geometry: { type: 'LineString', coordinates: path } })
    return { type: 'FeatureCollection', features }
}
