import { setWorkerUrl, type FilterSpecification } from "maplibre-gl"
import workerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url'
import type { ReactNode } from 'react'
import Map, { type MapRef } from 'react-map-gl/maplibre'
import 'maplibre-gl/dist/maplibre-gl.css'
import { sendError } from '../diagnostics/errorLog'
import { INITIAL_VIEW, MAX_ZOOM } from "./config"
import { style, styleError } from './mapStyle'
import { MAP_ID } from './missionMap'
import { hideGroups, narrowTrails, type StyleMetadata } from './styleChoices'

setWorkerUrl(workerUrl)

let tileErrorSent = false  // a tile failure repeats for every tile, so only the first is sent

type Props = {
    hidden: string[]        // the layer groups the user has hidden
    pickedUses: string[]    // the trail uses ticked; none ticked: all trails
    children?: ReactNode    // what is drawn on the map: mission layers and the tools' shapes
}

// react-map-gl calls this with the map as soon as it exists. Turning by keyboard and by two
// fingers has no setting on <Map>, so it is switched off here. Two-finger zoom still works.
function whenMapExists(ref: MapRef | null) {
    if (!ref) return
    const map = ref.getMap()
    map.keyboard.disableRotation()
    map.touchZoomRotate.disableRotation()
}

// The map. It puts itself on the shared board under MAP_ID, where the pieces outside it
// find it (useMissionMap).
function MissionMap({ hidden, pickedUses, children }: Props) {
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
            id={MAP_ID}
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
        >
            {children}
        </Map>
    )
}

export default MissionMap