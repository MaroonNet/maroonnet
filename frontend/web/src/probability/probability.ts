import { createContext, useContext } from 'react'
import { ask } from '../mission/mission.ts'

// A probability map as the backend answers it (backend/mapdb/routes.py): a picture, and
// where its four corners go on the map.
export type Corner = [number, number]  // longitude, then latitude: the order the map takes
export type Overlay = {
    id: string                                  // starts with the time it was made, UTC
    image: string                               // the picture's address
    coordinates: [Corner, Corner, Corner, Corner]  // top left, top right, bottom right, bottom left
}

// Whether the model can run on this computer, and what it can draw.
export type ModelStatus = {
    available: boolean
    detail: string                      // why not, when it cannot run
    models: Record<string, string[]>    // each fitted model, with the kinds of person it can draw
}

// What a map is made from.
export type MapRequest = {
    lon: number                 // the point the person was last known to be, or last seen
    lat: number
    model: string
    category: string            // the kind of person
    elapsed_h: number | null    // hours missing; none: the map takes no account of time
}

// The kinds of waypoint a map can be made from: the places a search starts out from.
export const STARTING_KINDS = ['last_known_position', 'point_last_seen']

// The model the app asks for, when it is there, and otherwise the first that can draw
// anyone. "model_a" is the one the backend itself uses when none is named.
const USUAL_MODEL = 'model_a'

// The model a map is made with and the kinds of person it can draw, or none when no
// fitted model can draw anyone.
export function pickModel(status: ModelStatus): { name: string, kinds: string[] } | null {
    const usable = Object.entries(status.models).filter(([, kinds]) => kinds.length > 0)
    const picked = usable.find(([name]) => name === USUAL_MODEL) ?? usable[0]
    return picked ? { name: picked[0], kinds: picked[1] } : null
}

// A kind of person as the form lists it: the model's own word, "child_7_12", as "Child 7 12".
export function personLabel(kind: string): string {
    const words = kind.replaceAll('_', ' ')
    return words.charAt(0).toUpperCase() + words.slice(1)
}

// The most hours missing the backend takes: thirty days.
export const MOST_HOURS = 720

export const loadOverlays = () => ask<Overlay[]>('/api/spm/predictions')  // newest first
export const loadModelStatus = () => ask<ModelStatus>('/api/spm/status')
export const makeOverlay = (request: MapRequest) => ask<Overlay>('/api/spm/predict', 'POST', request)

// The board: the open mission's probability map, kept in one place that any component can
// read. make answers with nothing when the map was made, and with the reason when it was
// not; the board changes only when it was made.
export type ProbabilityBoard = {
    newest: Overlay | null      // the newest map kept with the open mission; none made, or no mission open
    make: (request: MapRequest) => Promise<string>
}

// A component drawn with no ProbabilityProvider above it, as in a test of one component,
// reads this board: no map, and none can be made.
export const ProbabilityContext = createContext<ProbabilityBoard>({
    newest: null,
    make: async () => 'There is no probability board.',
})

// What a component calls to read the board.
export function useProbability(): ProbabilityBoard {
    return useContext(ProbabilityContext)
}
