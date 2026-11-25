import type { FeatureCollection } from 'geojson'
import { Layer, Source } from 'react-map-gl/maplibre'
import type { LayerChoice } from '../layers/missionLayers.ts'
import { useProbability } from './probability.ts'

type Props = {
    layer: LayerChoice      // the Layers panel's choice for Probability heatmap: shown or not, and how solid
}

// The layer that keeps the heatmap's place among the map's layers. It draws nothing.
const PLACE = 'heatmap-place'
const NOTHING: FeatureCollection = { type: 'FeatureCollection', features: [] }

// The probability heatmap on the map: the open mission's newest map, as one picture pinned
// by its four corners. The model draws the picture, colors and all; the map only places it.
// It is drawn inside the map (a child of MissionMap), and comes first there, so it lies
// over the basemap and under the search area line, the sectors and the tracks.
//
// The map library puts a new layer on top of the others. A map made, or read, after the
// sectors were drawn would then cover them. So an empty layer is put on the map at the
// start to keep the heatmap's place, and the picture always goes in just under it.
function HeatmapOnMap({ layer }: Props) {
    const { newest } = useProbability()
    return (
        <>
            <Source id={PLACE} type="geojson" data={NOTHING}>
                <Layer id={PLACE} type="line" />
            </Source>
            {newest && (
                // key: a new map is a new picture on the map, not the old one with another address.
                <Source key={newest.id} id="heatmap" type="image" url={newest.image} coordinates={newest.coordinates}>
                    <Layer
                        id="heatmap-picture"
                        type="raster"
                        beforeId={PLACE}
                        layout={{ visibility: layer.shown ? 'visible' : 'none' }}
                        // No fade: the picture shows at once when it is ticked or a new one is made.
                        paint={{ 'raster-opacity': layer.opacity, 'raster-fade-duration': 0 }}
                    />
                </Source>
            )}
        </>
    )
}

export default HeatmapOnMap
