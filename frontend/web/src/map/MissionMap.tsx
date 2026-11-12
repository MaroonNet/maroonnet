import { addProtocol, setWorkerUrl, type RasterDEMSourceSpecification, type StyleSpecification } from "maplibre-gl"
import workerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url'
import mlcontour from 'maplibre-contour'
import Map, { NavigationControl, ScaleControl } from 'react-map-gl/maplibre'
import 'maplibre-gl/dist/maplibre-gl.css'
import { sendError } from '../diagnostics/errorLog'
import { INITIAL_VIEW, MAP_STYLE_URL, MAX_ZOOM } from "./config"

setWorkerUrl(workerUrl)

// The contour plug-in's supply of height (DEM) tiles. It answers the style's dem-shared://
// address, downloading each terrain tile once for both the hillshade and the contour lines.
// Must be set up before the map loads its style.
//
// The style is fetched first because it says how deep the terrain goes, which the contour
// plug-in needs before the map loads the style. Each await waits for a promise (a placeholder
// for an answer still on its way) to be filled. They sit outside any function, so the whole
// file pauses at this line until the style arrives.
const style: StyleSpecification = await (await fetch(MAP_STYLE_URL)).json()
const terrain = style.sources.terrain as RasterDEMSourceSpecification

const demSource = new mlcontour.DemSource({
    url: `${location.origin}/tiles/terrain/{z}/{x}/{y}`,  // absolute: the plug-in fetches from a worker
    encoding: 'terrarium',
    maxzoom: terrain.maxzoom!,  // the backend always sets it
    worker: true,
})
demSource.setupMaplibre({ addProtocol })

let tileErrorSent = false  // a tile failure repeats for every tile, so only the first is sent

function MissionMap() {
    return (
        <Map
            initialViewState={INITIAL_VIEW}
            mapStyle={style}
            maxZoom={MAX_ZOOM}
            style={{width: '100%', height: '100%'}}
            onError={(e) => {
                if ('tile' in e) {
                    if (tileErrorSent) return
                    tileErrorSent = true
                }
                sendError('map', e.error?.stack ?? e.error)
            }}
        >
            <NavigationControl position="top-right" />
            <ScaleControl />
        </Map>
    )
}

export default MissionMap