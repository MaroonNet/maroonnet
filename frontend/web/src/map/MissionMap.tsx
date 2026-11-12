import { addProtocol, setWorkerUrl, type LayerSpecification, type RasterDEMSourceSpecification, type StyleSpecification } from "maplibre-gl"
import { useState } from 'react'
import workerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url'
import mlcontour from 'maplibre-contour'
import Map, { NavigationControl, ScaleControl } from 'react-map-gl/maplibre'
import 'maplibre-gl/dist/maplibre-gl.css'
import { sendError } from '../diagnostics/errorLog'
import { INITIAL_VIEW, MAP_STYLE_URL, MAX_ZOOM } from "./config"
import LayerToggles from './LayerToggles'

setWorkerUrl(workerUrl)

// The style is fetched first because it says how deep the terrain goes, which the contour
// plug-in needs before the map loads the style. Each await waits for a promise (a placeholder
// for an answer still on its way) to be filled. They sit outside any function, so the whole
// file pauses here until the style arrives or fails.
let style: StyleSpecification | null = null
let styleError = ''  // why the style failed, shown on the page
try {
    const response = await fetch(MAP_STYLE_URL)
    if (!response.ok) throw new Error(`${response.status} ${response.statusText}`)  // an answer, but an error
    style = await response.json()
} catch (error) {
    styleError = String(error)
    sendError('style', error)
}

// The contour plug-in's supply of height (DEM) tiles. It answers the style's dem-shared://
// address, downloading each terrain tile once for both the hillshade and the contour lines.
// Must be set up before the map loads its style.
if (style) {
    const terrain = style.sources.terrain as RasterDEMSourceSpecification
    const demSource = new mlcontour.DemSource({
        url: `${location.origin}/tiles/terrain/{z}/{x}/{y}`,  // absolute: the plug-in fetches from a worker
        encoding: 'terrarium',
        maxzoom: terrain.maxzoom!,  // the backend always sets it
        worker: true,
    })
    demSource.setupMaplibre({ addProtocol })
}

let tileErrorSent = false  // a tile failure repeats for every tile, so only the first is sent

// A copy of the style with the hidden groups' layers set to not show. MapLibre compares it
// with the style it is drawing and changes only those layers.
function hideGroups(style: StyleSpecification, hidden: string[]): StyleSpecification {
    return {
        ...style,
        layers: style.layers.map((layer) => {
            const group = (layer.metadata as { group?: string } | undefined)?.group
            if (!group || !hidden.includes(group)) return layer
            return { ...layer, layout: { ...layer.layout, visibility: 'none' } } as LayerSpecification
        }),
    }
}

function MissionMap() {
    const [hidden, setHidden] = useState<string[]>([])  // the layer groups the user has hidden

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
            initialViewState={INITIAL_VIEW}
            mapStyle={hideGroups(style, hidden)}
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
            <LayerToggles hidden={hidden} setHidden={setHidden} />
        </Map>
    )
}

export default MissionMap