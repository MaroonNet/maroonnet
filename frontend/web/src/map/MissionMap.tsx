import { setWorkerUrl, type FilterSpecification, type Map as MapLibreMap } from "maplibre-gl"
import workerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url'
import { useCallback } from 'react'
import Map, { type MapRef } from 'react-map-gl/maplibre'
import 'maplibre-gl/dist/maplibre-gl.css'
import { sendError } from '../diagnostics/errorLog'
import { INITIAL_VIEW, MAX_ZOOM } from "./config"
import { style, styleError } from './mapStyle'
import { hideGroups, narrowTrails, type StyleMetadata } from './styleChoices'

setWorkerUrl(workerUrl)

let tileErrorSent = false  // a tile failure repeats for every tile, so only the first is sent

type Props = {
    hidden: string[]        // the layer groups the user has hidden
    pickedUses: string[]    // the trail uses ticked; none ticked: all trails
    onMap: (map: MapLibreMap) => void  // called once with the MapLibre map, as soon as it exists
}

function MissionMap({ hidden, pickedUses, onMap }: Props) {
    // react-map-gl calls this with the map as soon as it exists, before its tiles have loaded,
    // so the controls outside the map can show straight away. useCallback keeps it the same
    // function between redraws, so it is called once and not on every redraw.
    const whenMapExists = useCallback((ref: MapRef | null) => {
        if (!ref) return
        const map = ref.getMap()
        // Turning by keyboard and by two fingers has no setting on <Map>, so it is switched
        // off here. Two-finger zoom still works.
        map.keyboard.disableRotation()
        map.touchZoomRotate.disableRotation()
        onMap(map)
    }, [onMap])

    if (!style) {
        return (
            <p style={{ padding: 16, font: '14px system-ui, sans-serif' }}>
                The map could not load its style from the backend ({styleError}).
                Check that the backend is running, then reload the page.
            </p>
        )
    }
    const metadata = style.metadata as StyleMetadata  // the backend always sets it
    // A trail open to any ticked use is drawn.
    const pickedFilters = metadata.trail_uses.filter((use) => pickedUses.includes(use.id)).map((use) => use.filter)
    const trailFilter = pickedFilters.length ? ['any', ...pickedFilters] as FilterSpecification : undefined
    return (
        <Map
            ref={whenMapExists}
            initialViewState={INITIAL_VIEW}
            mapStyle={narrowTrails(hideGroups(style, hidden), trailFilter)}
            maxZoom={MAX_ZOOM}
            dragRotate={false}  // north stays up: no turning with the mouse,
            maxPitch={0}        // and no tilting
            attributionControl={{ compact: true }}  // the data credits only, without MapLibre's own link
            style={{width: '100%', height: '100%'}}
            onError={(e) => {
                console.error(e.error)  // every error, as react-map-gl prints when there is no onError
                if ('tile' in e) {
                    if (tileErrorSent) return
                    tileErrorSent = true
                }
                sendError('map', e.error)
            }}
        />
    )
}

export default MissionMap