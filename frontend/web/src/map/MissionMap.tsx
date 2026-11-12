import { addProtocol, setWorkerUrl } from "maplibre-gl"
import workerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url'
import mlcontour from 'maplibre-contour'
import Map, { NavigationControl, ScaleControl } from 'react-map-gl/maplibre'
import 'maplibre-gl/dist/maplibre-gl.css'
import { INITIAL_VIEW, MAP_STYLE_URL, MAX_ZOOM, TERRAIN_MAX_ZOOM } from "./config"

setWorkerUrl(workerUrl)

// The contour plug-in's supply of height (DEM) tiles. It answers the style's dem-shared://
// address, downloading each terrain tile once for both the hillshade and the contour lines.
// Must be set up before the map loads its style.
const demSource = new mlcontour.DemSource({
    url: `${location.origin}/tiles/terrain/{z}/{x}/{y}`,  // absolute: the plug-in fetches from a worker
    encoding: 'terrarium',
    maxzoom: TERRAIN_MAX_ZOOM,
    worker: true,
})
demSource.setupMaplibre({ addProtocol })

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