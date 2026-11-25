import { createContext, useContext } from 'react'
import { ask } from '../mission/mission.ts'

// A track as the backend answers it (backend/teams/tracks.py): everywhere a searcher radio
// reported from in the open session, in time order, cut where the radio changed group.
export type TrackPiece = {
    group_id: number | null         // the group the radio was in while it walked this piece
    // Each point is longitude, then latitude: the order the map takes. A piece after the
    // first starts on the last point of the piece before it.
    points: [number, number][]
}

export type Track = {
    radio_id: number
    pieces: TrackPiece[]
}

export const loadTracks = () => ask<Track[]>('/api/mission/tracks')

// The board: the open mission's tracks, kept in one place that any component can read.
// There are none while no mission is open, and none in a mission whose radios have not
// reported. A component drawn with no TracksProvider above it reads none.
export const TracksContext = createContext<Track[]>([])

// What a component calls to read the board.
export function useTracks(): Track[] {
    return useContext(TracksContext)
}
