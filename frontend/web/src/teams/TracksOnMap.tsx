import type { ExpressionSpecification } from 'maplibre-gl'
import type { Feature, FeatureCollection, LineString } from 'geojson'
import { useMemo } from 'react'
import { Layer, Source } from 'react-map-gl/maplibre'
import { teamColor } from './teamWords.ts'
import { useTracks, type Track } from './tracks.ts'

type Props = {
    selected: number | null     // the radio of the selected team: its track is drawn stronger, the rest fade
}

// The tracks walked, on the map: a line for each piece of each track, in the color of the
// group the radio was in while it walked that piece, and grey while it was in none. Where
// reports are missing the line goes straight on to the next one. It is drawn inside the map
// (a child of MissionMap), above the sectors. A track cannot be pressed: a team is picked
// by its marker or in the Groups & Teams panel.
function TracksOnMap({ selected }: Props) {
    const tracks = useTracks()
    // The lines are thousands of points, so they are built once for each set of tracks, not
    // each time something else on the screen changes.
    const lines = useMemo(() => trackLines(tracks), [tracks])
    const isSelected: ExpressionSpecification = ['==', ['get', 'radio'], selected ?? -1]
    return (
        <Source id="tracks" type="geojson" data={lines}>
            <Layer
                id="tracks-line"
                type="line"
                layout={{
                    'line-join': 'round',
                    'line-cap': 'round',
                    'line-sort-key': ['case', isSelected, 1, 0],  // the selected track is drawn last, on top
                }}
                paint={{
                    'line-color': ['get', 'color'],
                    'line-width': ['case', isSelected, 4.5, 2.5],
                    'line-opacity': selected === null ? 0.85 : ['case', isSelected, 1, 0.25],
                }}
            />
        </Source>
    )
}

// The tracks as lines the map can draw. A piece of one point is no line, so it is left off.
function trackLines(tracks: Track[]): FeatureCollection<LineString> {
    const lines = tracks.flatMap((track) => track.pieces
        .filter((piece) => piece.points.length > 1)
        .map((piece): Feature<LineString> => ({
            type: 'Feature',
            properties: { radio: track.radio_id, color: teamColor(piece.group_id) },
            geometry: { type: 'LineString', coordinates: piece.points },
        })))
    return { type: 'FeatureCollection', features: lines }
}

export default TracksOnMap
