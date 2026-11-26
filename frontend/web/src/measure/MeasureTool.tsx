import type { FeatureCollection } from 'geojson'
import type { MapMouseEvent } from 'maplibre-gl'
import { useEffect, useState } from 'react'
import { createPortal } from 'react-dom'
import { Layer, Marker, Source } from 'react-map-gl/maplibre'
import HintLine from '../frame/HintLine.tsx'
import { bearingDegrees, distanceMeters, type Position } from '../map/geo.ts'
import { useMissionMap } from '../map/missionMap.ts'
import { formatBearing } from '../map/position.ts'
import { useSettings } from '../settings/settings.ts'
import { formatDistance } from '../settings/units.ts'

type Props = {
    hintSlot: HTMLElement | null    // the spot under the toolbar where the hint line goes
}

// A measurement: where it starts, where it ends, and whether the end has been clicked or
// is still following the pointer.
type Measurement = { start: Position, end: Position | null, fixed: boolean }

const INK = '#201e18'  // --color-ink in index.css; the map takes colors as text

// The Measure tool, drawn inside the map while it is the picked tool. A click sets the
// start point and a second click the end point; a label at the end shows the distance and
// the bearing from the first point, from true north. One line shows at a time: a third
// click starts again, and Escape or leaving the tool clears it. Nothing is saved.
function MeasureTool({ hintSlot }: Props) {
    const map = useMissionMap()
    const { units } = useSettings().settings
    const [measured, setMeasured] = useState<Measurement | null>(null)

    // The map tells the tool about clicks and the pointer moving while the tool is picked.
    useEffect(() => {
        if (!map) return
        const placeOf = (event: MapMouseEvent): Position => ({ lat: event.lngLat.lat, lon: event.lngLat.lng })

        function onClick(event: MapMouseEvent) {
            const place = placeOf(event)
            // The first click, or a click after a finished line, starts a measurement.
            // The click in between ends it.
            setMeasured((now) => !now || now.fixed ? { start: place, end: null, fixed: false } : { ...now, end: place, fixed: true })
        }
        function onMove(event: MapMouseEvent) {
            const place = placeOf(event)
            setMeasured((now) => now && !now.fixed ? { ...now, end: place } : now)
        }

        map.on('click', onClick)
        map.on('mousemove', onMove)
        map.getCanvas().style.cursor = 'crosshair'
        map.doubleClickZoom.disable()  // two quick clicks are two points, not a zoom
        return () => {
            map.off('click', onClick)
            map.off('mousemove', onMove)
            map.getCanvas().style.cursor = ''
            map.doubleClickZoom.enable()
        }
    }, [map])

    useEffect(() => {
        function onKeyDown(event: KeyboardEvent) {
            if (event.key === 'Escape') setMeasured(null)
        }
        window.addEventListener('keydown', onKeyDown)
        return () => window.removeEventListener('keydown', onKeyDown)
    }, [])

    const { start, end, fixed } = measured ?? { start: null, end: null, fixed: false }
    const figure = start && end ? `${formatDistance(distanceMeters(start, end), units)} · ${formatBearing(bearingDegrees(start, end))}` : undefined
    const hint = !start ? 'Click the start point.' : !fixed ? 'Click the end point.' : 'Click to measure again, or press Escape to clear.'
    return (
        <>
            {/* A portal draws the hint line in another part of the page: its spot under the toolbar. */}
            {hintSlot && createPortal(<HintLine text={hint} figure={fixed ? undefined : figure} />, hintSlot)}
            {start && (
                <Source id="measure" type="geojson" data={shapes(start, end)}>
                    <Layer id="measure-line" type="line" filter={['==', ['geometry-type'], 'LineString']} paint={{ 'line-color': INK, 'line-width': 2 }} />
                    <Layer
                        id="measure-points"
                        type="circle"
                        filter={['==', ['geometry-type'], 'Point']}
                        paint={{ 'circle-radius': 4, 'circle-color': '#f9f5e9', 'circle-stroke-color': INK, 'circle-stroke-width': 2 }}
                    />
                </Source>
            )}
            {fixed && end && (
                // The label sits to the right of the end point, and lets clicks through to the map.
                <Marker latitude={end.lat} longitude={end.lon} anchor="left" offset={[10, 0]} style={{ pointerEvents: 'none' }}>
                    <div className="rounded-control bg-ink px-2 py-1 text-input font-medium whitespace-nowrap text-panel tabular-nums">{figure}</div>
                </Marker>
            )}
        </>
    )
}

// The measurement as shapes the map can draw: the line, and a dot at each end. The map
// takes longitude before latitude.
function shapes(start: Position, end: Position | null): FeatureCollection {
    const corners = [start, ...(end ? [end] : [])].map((place) => [place.lon, place.lat])
    return {
        type: 'FeatureCollection',
        features: [
            ...(end ? [{ type: 'Feature' as const, properties: {}, geometry: { type: 'LineString' as const, coordinates: corners } }] : []),
            ...corners.map((corner) => ({ type: 'Feature' as const, properties: {}, geometry: { type: 'Point' as const, coordinates: corner } })),
        ],
    }
}

export default MeasureTool
