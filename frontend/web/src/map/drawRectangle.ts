import type { Map as MapLibreMap } from 'maplibre-gl'
import { TerraDraw, TerraDrawRectangleMode } from 'terra-draw'
import { TerraDrawMapLibreGLAdapter } from 'terra-draw-maplibre-gl-adapter'
import type { Bounds } from './geo.ts'

// A rectangle being drawn on the map.
export type RectangleDrawing = {
    clear: () => void   // takes the rectangle off the map; the next drag starts a new one
    stop: () => void    // ends the drawing: the rectangle goes, and a drag moves the map again
}

type Listeners = {
    drag: (box: Bounds) => void     // the rectangle so far, each time the pointer moves
    finish: (box: Bounds) => void   // the finished rectangle, when the button is let go
}

const INK = '#201e18'  // --color-ink in index.css; the drawing library takes colors as text

// Lets the user drag out one rectangle on the map, with the drawing library Terra Draw.
// While this runs, pressing and dragging draws and does not move the map. The finished
// rectangle stays on the map until the next drag starts, or clear or stop is called.
export function drawRectangle(map: MapLibreMap, on: Listeners): RectangleDrawing {
    const draw = new TerraDraw({
        adapter: new TerraDrawMapLibreGLAdapter({ map }),
        modes: [new TerraDrawRectangleMode({
            drawInteraction: 'click-drag',  // press, drag, let go
            styles: { fillColor: INK, fillOpacity: 0.08, outlineColor: INK, outlineWidth: 2 },
        })],
    })
    let finished: string | number | null = null  // the id of the rectangle left on the map

    // Terra Draw reports every change to its shapes here.
    draw.on('change', (ids, type) => {
        if (type === 'delete') return
        if (type === 'create' && finished !== null) {
            // A new drag has started, so the rectangle from the last one goes.
            const last = finished
            finished = null
            draw.removeFeatures([last])
        }
        const box = boundsOf(draw, ids[0])
        if (box) on.drag(box)
    })

    draw.on('finish', (id) => {
        const box = boundsOf(draw, id)
        if (!box) {
            draw.removeFeatures([id])  // a press with no drag: nothing was drawn
            return
        }
        finished = id
        on.finish(box)
    })

    // Terra Draw adds its layers to the map's style, which must have loaded first. If it has
    // not, the drawing starts when the map next comes to rest ("idle").
    let stopped = false
    function start() {
        if (stopped) return
        draw.start()
        draw.setMode('rectangle')
    }
    if (map.isStyleLoaded()) start()
    else map.once('idle', start)

    return {
        clear() {
            finished = null
            if (draw.enabled) draw.clear()
        },
        stop() {
            stopped = true
            if (draw.enabled) draw.stop()
        },
    }
}

// The corners of one drawn rectangle, or nothing while it has no width or no height.
function boundsOf(draw: TerraDraw, id: string | number): Bounds | null {
    const shape = draw.getSnapshotFeature(id)
    if (shape?.geometry.type !== 'Polygon') return null
    const corners = shape.geometry.coordinates[0]  // each is [longitude, latitude]
    const lons = corners.map((corner) => corner[0])
    const lats = corners.map((corner) => corner[1])
    const box = { min_lat: Math.min(...lats), min_lon: Math.min(...lons), max_lat: Math.max(...lats), max_lon: Math.max(...lons) }
    return box.min_lat < box.max_lat && box.min_lon < box.max_lon ? box : null
}
