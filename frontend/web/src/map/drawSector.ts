import type { Polygon } from 'geojson'
import type { Map as MapLibreMap } from 'maplibre-gl'
import { TerraDraw, TerraDrawPolygonMode, TerraDrawRectangleMode, TerraDrawSelectMode, type GeoJSONStoreFeatures } from 'terra-draw'
import { TerraDrawMapLibreGLAdapter } from 'terra-draw-maplibre-gl-adapter'
import { onOrInside, type Bounds, type Position } from './geo.ts'
import { MOST_CORNERS } from './shapeDraft.ts'

// The two ways to draw a sector: drag out a rectangle, or click its corners one at a time
// (drawCustomShape.ts).
export type SectorShape = 'rectangle' | 'custom'

// A sector being drawn on the map.
export type SectorDrawing = {
    discard: () => void  // takes the shape off the map; the next drag starts a new one
    stop: () => void     // ends the drawing: the shape goes, and a drag moves the map again
    // Puts a finished shape on the map with its corners ready to drag, as a drawn rectangle's
    // are: a custom shape once closed.
    edit: (corners: Position[]) => void
}

type Listeners = {
    change: (corners: Position[]) => void  // the shape so far: while dragged out, and while a corner is dragged or added
    finish?: (corners: Position[]) => void // a rectangle is drawn; its corners can now be dragged
    outside?: () => void                   // a rectangle was let go wholly outside the search area, so nothing was drawn
    full?: () => void                      // a corner added at a side's middle was refused: the shape has 24
}

const RED = '#c9302d'  // a drawn sector's red (SECTOR_COLORS in sectors/looks.ts)

// Terra Draw's name for a shape that came in by edit(). The polygon mode is registered so
// such a shape belongs to a mode, but it is never turned on: a custom shape is clicked out
// by drawCustomShape.ts, which keeps the rules for corners.
const GIVEN = 'polygon'

// Lets the user draw one sector on the map, kept inside the search area, with the drawing
// library Terra Draw. For a rectangle, pressing and dragging draws it; once it is let go,
// each corner can be dragged. A custom shape is handed over by edit() once closed. Nothing
// goes past the search area line: an edge of the rectangle past it is brought back onto it,
// and a dragged corner slides along it. A dragged corner cannot make two sides cross.
export function drawSector(map: MapLibreMap, area: Bounds, shape: SectorShape, on: Listeners): SectorDrawing {
    // Where a pointer past the line is taken to be: the nearest place on the line.
    const keepInside = ({ lng, lat }: { lng: number, lat: number }) => {
        const place = onOrInside({ lat, lon: lng }, area)
        return [place.lon, place.lat]
    }
    // How a finished shape's corners may be dragged. A dot at the middle of each side adds a
    // corner there when dragged, up to the 24 a sector may have.
    const dragCorners = {
        feature: {
            selfIntersectable: false,  // a drag that would cross two sides is not taken
            validation: (shape: GeoJSONStoreFeatures) => {
                const corners = (shape.geometry as Polygon).coordinates[0].length - 1  // the ring repeats its first corner
                if (corners <= MOST_CORNERS) return { valid: true }
                on.full?.()
                return { valid: false, reason: `A sector has at most ${MOST_CORNERS} corners.` }
            },
            coordinates: {
                draggable: true,
                snappable: { toCustom: keepInside },
                midpoints: { draggable: true },
                deletable: false,   // no corners taken away
            },
        },
    }
    const draw = new TerraDraw({
        adapter: new TerraDrawMapLibreGLAdapter({ map }),
        modes: [
            new TerraDrawRectangleMode({
                drawInteraction: 'click-drag',  // press, drag, let go
                styles: { fillColor: RED, fillOpacity: 0.08, outlineColor: RED, outlineWidth: 2 },
            }),
            new TerraDrawPolygonMode({ styles: { fillColor: RED, fillOpacity: 0.08, outlineColor: RED, outlineWidth: 2 } }),
            // Once drawn, the shape is held "selected", which shows its corners as handles.
            // Only this code selects it, and a click elsewhere does not let it go.
            new TerraDrawSelectMode({
                allowManualSelection: false,
                allowManualDeselection: false,
                keyEvents: null,  // no keys: Delete and Escape are the tool's own
                flags: { rectangle: dragCorners, [GIVEN]: dragCorners },
                styles: {
                    selectedPolygonColor: RED, selectedPolygonFillOpacity: 0.08,
                    selectedPolygonOutlineColor: RED, selectedPolygonOutlineWidth: 2,
                    selectionPointColor: '#ffffff', selectionPointOutlineColor: RED,
                    selectionPointWidth: 5, selectionPointOutlineWidth: 2,
                    // The dot at a side's middle, smaller and solid, so it reads apart from a corner.
                    midPointColor: RED, midPointOutlineColor: '#ffffff', midPointWidth: 3, midPointOutlineWidth: 1,
                },
            }),
        ],
    })
    let drawn: string | number | null = null  // the id of the finished shape, while its corners can be dragged

    // Terra Draw reports every change to its shapes here, including the corner handles it
    // draws itself; only the sector's own shape is passed on.
    draw.on('change', (ids) => {
        const id = ids[0]
        const corners = sectorCorners(draw, id)
        if (!corners) return
        if (drawn === null || id === drawn) on.change(corners.map((corner) => onOrInside(corner, area)))
    })

    draw.on('finish', (id, context) => {
        if (context.mode !== 'rectangle') return  // a corner drag ended; change has reported it
        const corners = sectorCorners(draw, id)
        if (!corners || !hasArea(corners)) {
            draw.removeFeatures([id])  // a press with no drag: nothing was drawn
            return
        }
        const inside = corners.map((corner) => onOrInside(corner, area))
        if (!hasArea(inside)) {
            draw.removeFeatures([id])
            on.outside?.()
            return
        }
        draw.updateFeatureGeometry(id, ringOf(inside))
        holdForEditing(id)
        on.finish?.(inside)
    })

    // The shape's corners become handles to drag.
    function holdForEditing(id: string | number) {
        drawn = id
        draw.setMode('select')
        draw.selectFeature(id)
    }

    // Terra Draw adds its layers to the map's style, which must have loaded first. If it has
    // not, the drawing starts when the map next comes to rest ("idle"). For a custom shape
    // Terra Draw has nothing to do until the shape is closed, so it starts then, and the
    // clicks that place the corners reach the map untouched.
    let stopped = false
    function start() {
        if (stopped || draw.enabled) return
        draw.start()
        draw.setMode(shape === 'rectangle' ? 'rectangle' : 'select')
    }
    if (shape === 'rectangle') {
        if (map.isStyleLoaded()) start()
        else map.once('idle', start)
    }

    return {
        discard() {
            if (!draw.enabled) return
            drawn = null
            draw.clear()
            draw.setMode(shape === 'rectangle' ? 'rectangle' : 'select')
        },
        stop() {
            stopped = true
            if (draw.enabled) draw.stop()
        },
        edit(corners) {
            start()
            const [added] = draw.addFeatures([{ type: 'Feature', geometry: ringOf(corners), properties: { mode: GIVEN } }])
            if (added?.valid && added.id !== undefined) holdForEditing(added.id)
            else console.error('The drawing library refused the shape:', added?.reason)
        },
    }
}

// Terra Draw keeps no more than nine decimal places of a degree (about a millimeter), and
// refuses a shape with more. A map click gives about fifteen.
const PLACES = 1e9
const rounded = (degrees: number) => Math.round(degrees * PLACES) / PLACES

// The corners as a shape Terra Draw keeps: longitude first, and back to the first corner.
function ringOf(corners: Position[]): Polygon {
    return { type: 'Polygon', coordinates: [[...corners, corners[0]].map(({ lat, lon }) => [rounded(lon), rounded(lat)])] }
}

// The corners of the sector's shape, without the ring's repeat of the first, or nothing
// when this id is not the sector (a corner handle, or a shape already removed).
function sectorCorners(draw: TerraDraw, id: string | number): Position[] | null {
    const shape = draw.getSnapshotFeature(id)
    const mode = shape?.properties.mode
    if (shape?.geometry.type !== 'Polygon' || (mode !== 'rectangle' && mode !== GIVEN)) return null
    const ring = (shape.geometry as Polygon).coordinates[0]
    return ring.slice(0, -1).map(([lon, lat]) => ({ lat, lon }))
}

// Whether the corners enclose some ground: not all on one line of latitude or longitude.
function hasArea(corners: Position[]): boolean {
    const lats = corners.map((corner) => corner.lat), lons = corners.map((corner) => corner.lon)
    return Math.min(...lats) < Math.max(...lats) && Math.min(...lons) < Math.max(...lons)
}
