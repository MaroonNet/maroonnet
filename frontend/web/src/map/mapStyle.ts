import { addProtocol, type RasterDEMSourceSpecification, type StyleSpecification } from 'maplibre-gl'
import mlcontour from 'maplibre-contour'
import { sendError } from '../diagnostics/errorLog'
import { MAP_STYLE_URL } from './config'

// The map style, fetched once when the page opens. The map draws from it, and the Layers panel
// reads its lists of layer groups and trail uses.

// The style is fetched first because it says how deep the terrain goes, which the contour
// plug-in needs before the map loads the style. Each await waits for a promise (a placeholder
// for an answer still on its way) to be filled. They sit outside any function, so every file
// that imports this one pauses here until the style arrives or fails.
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

export { style, styleError }
