import { setWorkerUrl } from "maplibre-gl"
import workerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url'
import Map, { NavigationControl, ScaleControl } from 'react-map-gl/maplibre'
import 'maplibre-gl/dist/maplibre-gl.css'
import { INITIAL_VIEW, MAP_STYLE_URL, MAX_ZOOM } from "./config"

setWorkerUrl(workerUrl)

function MissionMap() {
    return (
        <Map
            initialViewState={INITIAL_VIEW}
            mapStyle={MAP_STYLE_URL}
            maxZoom={MAX_ZOOM}
            style={{width: '100%', height: '100%'}}
        >
            <NavigationControl position="top-right" />
            <ScaleControl />
        </Map>
    )
}

export default MissionMap