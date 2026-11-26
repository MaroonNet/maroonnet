import { setWorkerUrl, type StyleSpecification } from "maplibre-gl"
import workerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url'
import { useEffect, useRef, type ReactNode } from 'react'
import Map, { type MapRef } from 'react-map-gl/maplibre'
import 'maplibre-gl/dist/maplibre-gl.css'
import { sendError } from '../diagnostics/errorLog'
import { INITIAL_VIEW, MAX_ZOOM } from "./config"
import { style, styleError } from './mapStyle'
import { MAP_ID, useMissionMap } from './missionMap'
import { hideGroups, keepAdded } from './styleChoices'

setWorkerUrl(workerUrl)

let tileErrorSent = false  // a tile failure repeats for every tile, so only the first is sent

type Props = {
    hidden: string[]        // the layer groups the user has hidden
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
function MissionMap({ hidden, children }: Props) {
    if (!style) {
        return (
            <p style={{ padding: 16, font: '14px system-ui, sans-serif' }}>
                The map could not load its style from the backend ({styleError}).
                Check that the backend is running, then reload the page.
            </p>
        )
    }
    return (
        <Map
            id={MAP_ID}
            ref={whenMapExists}
            initialViewState={INITIAL_VIEW}
            mapStyle={style}  // the backend's style, as it came; LayerChoices changes it on the map
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
            <LayerChoices base={style} hidden={hidden} />
            {children}
        </Map>
    )
}

type LayerChoicesProps = {
    base: StyleSpecification    // the backend's style
    hidden: string[]
}

// Applies the Layers panel's choices to the map. It draws nothing itself. Each time a choice
// changes it hands the map a copy of the style with the choices made, and MapLibre changes
// only what differs. keepAdded puts back what was added to the map since it loaded (a tool's
// drawing, the mission's layers), which MapLibre would otherwise take away.
function LayerChoices({ base, hidden }: LayerChoicesProps) {
    const map = useMissionMap()
    const untouched = useRef(true)  // no choice has been made yet, so the map draws the style as it came

    useEffect(() => {
        if (!map) return
        if (untouched.current && !hidden.length) return
        untouched.current = false
        map.setStyle(hideGroups(base, hidden), {
            diff: true,
            transformStyle: (previous, next) => keepAdded(base, previous, next),
        })
    }, [map, base, hidden])

    return null
}

export default MissionMap