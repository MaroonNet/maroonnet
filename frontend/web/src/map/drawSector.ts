import type { Polygon } from 'geojson'
import type { Map as MapLibreMap } from 'maplibre-gl'
import { TerraDraw, TerraDrawRectangleMode, TerraDrawSelectMode } from 'terra-draw'
import { TerraDrawMapLibreGLAdapter } from 'terra-draw-maplibre-gl-adapter'
import { onOrInside, type Bounds, type Position } from './geo.ts'

// A sector being drawn on the map.
export type SectorDrawing = {
    discard: () => void  // takes the shape off the map; the next drag starts a new one
    stop: () => void     // ends the drawing: the shape goes, and a drag moves the map again
}

type Listeners = {
    change: (corners: Position[]) => void  // the shape so far: while dragged out, and while a corner is dragged
    finish: (corners: Position[]) => void  // the shape is drawn; its corners can now be dragged
    outside: () => void                    // a rectangle was let go wholly outside the search area, so nothing was drawn
}

const RED = '#c9302d'  // a drawn sector's red (SECTOR_COLORS in sectors/looks.ts)

// Lets the user draw one sector on the map, kept inside the search area, with the drawing
// library Terra Draw. Pressing and dragging draws a rectangle; once it is let go, each
// corner can be dragged. Nothing goes past the search area line: an edge of the rectangle
// past it is brought back onto it, and a dragged corner slides along it. A dragged corner
// cannot make two sides cross.
export function drawSector(map: MapLibreMap, area: Bounds, on: Listeners): SectorDrawing {
    // Where a pointer past the line is taken to be: the nearest place on the line.
    const keepInside = ({ lng, lat }: { lng: number, lat: number }) => {
        const place = onOrInside({ lat, lon: lng }, area)
        return [place.lon, place.lat]
    }
    const draw = new TerraDraw({
        adapter: new TerraDrawMapLibreGLAdapter({ map }),
        modes: [
            new TerraDrawRectangleMode({
                drawInteraction: 'click-drag',  // press, drag, let go
                styles: { fillColor: RED, fillOpacity: 0.08, outlineColor: RED, outlineWidth: 2 },
            }),
            // Once drawn, the shape is held "selected", which shows its corners as handles.
            // Only this code selects it, and a click elsewhere does not let it go.
            new TerraDrawSelectMode({
                allowManualSelection: false,
                allowManualDeselection: false,
                keyEvents: null,  // no keys: Delete and Escape are the tool's own
                flags: {
                    rectangle: {
                        feature: {
                            selfIntersectable: false,  // a drag that would cross two sides is not taken
                            coordinates: {
                                draggable: true,
                                snappable: { toCustom: keepInside },
                                midpoints: false,   // no corners added by dragging a side's middle
                                deletable: false,   // and none taken away
                            },
                        },
                    },
                },
                styles: {
                    selectedPolygonColor: RED, selectedPolygonFillOpacity: 0.08,
                    selectedPolygonOutlineColor: RED, selectedPolygonOutlineWidth: 2,
                    selectionPointColor: '#ffffff', selectionPointOutlineColor: RED,
                    selectionPointWidth: 5, selectionPointOutlineWidth: 2,
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
            on.outside()
            return
        }
        const ring = [...inside, inside[0]].map(({ lat, lon }) => [lon, lat])
        draw.updateFeatureGeometry(id, { type: 'Polygon', coordinates: [ring] })
        drawn = id
        draw.setMode('select')
        draw.selectFeature(id)
        on.finish(inside)
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
        discard() {
            if (!draw.enabled) return
            drawn = null
            draw.clear()
            draw.setMode('rectangle')
        },
        stop() {
            stopped = true
            if (draw.enabled) draw.stop()
        },
    }
}

// The corners of the sector's shape, without the ring's repeat of the first, or nothing
// when this id is not the sector (a corner handle, or a shape already removed).
function sectorCorners(draw: TerraDraw, id: string | number): Position[] | null {
    const shape = draw.getSnapshotFeature(id)
    if (shape?.geometry.type !== 'Polygon' || shape.properties.mode !== 'rectangle') return null
    const ring = (shape.geometry as Polygon).coordinates[0]
    return ring.slice(0, -1).map(([lon, lat]) => ({ lat, lon }))
}

// Whether the corners enclose some ground: not all on one line of latitude or longitude.
function hasArea(corners: Position[]): boolean {
    const lats = corners.map((corner) => corner.lat), lons = corners.map((corner) => corner.lon)
    return Math.min(...lats) < Math.max(...lats) && Math.min(...lons) < Math.max(...lons)
}
