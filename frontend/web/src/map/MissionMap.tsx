import { setWorkerUrl, type FilterSpecification } from "maplibre-gl"
import workerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url'
import Map, { NavigationControl, ScaleControl } from 'react-map-gl/maplibre'
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
}

function MissionMap({ hidden, pickedUses }: Props) {
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
            initialViewState={INITIAL_VIEW}
            mapStyle={narrowTrails(hideGroups(style, hidden), trailFilter)}
            maxZoom={MAX_ZOOM}
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
            <NavigationControl position="top-right" />
            <ScaleControl />
        </Map>
    )
}

export default MissionMap