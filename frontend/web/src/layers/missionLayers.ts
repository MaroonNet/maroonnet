// The mission layers: what the app itself draws on the map, over the basemap. The Layers
// panel has a row for each, with a checkbox and an opacity slider.
export type MissionLayerId = 'sectors' | 'teams' | 'tracks' | 'waypoints' | 'heatmap'

// How one layer is drawn: whether it shows, and how solid, from 0 (clear) to 1 (as drawn).
export type LayerChoice = { shown: boolean, opacity: number }

export type MissionLayerChoices = Record<MissionLayerId, LayerChoice>

// In the order the panel lists them.
export const MISSION_LAYERS: { id: MissionLayerId, label: string }[] = [
    { id: 'sectors', label: 'Sectors' },
    { id: 'teams', label: 'Team positions' },
    { id: 'tracks', label: 'Tracks walked' },
    { id: 'waypoints', label: 'Waypoints' },
    { id: 'heatmap', label: 'Probability heatmap' },
]

// A layer drawn in full. A map piece handed no choice is drawn this way.
export const SHOWN: LayerChoice = { shown: true, opacity: 1 }

// The choices when the app opens: everything shows but the heatmap, which covers the map
// under it and is ticked when it is wanted.
export const AS_OPENED: MissionLayerChoices = {
    sectors: SHOWN,
    teams: SHOWN,
    tracks: SHOWN,
    waypoints: SHOWN,
    heatmap: { shown: false, opacity: 1 },
}
