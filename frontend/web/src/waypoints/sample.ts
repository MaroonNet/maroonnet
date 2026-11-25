import type { Waypoint, WaypointsBoard } from './waypoints.ts'

// Pieces the tests build waypoints and a waypoints board from.

// A waypoint the commander placed at 8:40 pm Arizona time, with no description or note.
export function waypoint(id: number, kind: string, name: string, extra: Partial<Waypoint> = {}): Waypoint {
    return {
        id, kind, name, lat: 31.5 + id / 1000, lon: -110.67, description: null, note: null,
        time: '2025-04-14T03:40:00Z', created_time: '2025-04-14T03:40:00Z', radio_id: null, ...extra,
    }
}

// Arizona07's six waypoints. The two finds are about 4 m apart.
export const ARIZONA07: Waypoint[] = [
    waypoint(1, 'command_post', 'Command post', { lat: 31.5062579, lon: -110.6775338 }),
    waypoint(2, 'last_known_position', 'Start point', { lat: 31.5057167, lon: -110.6762167, description: 'Initial planning point from the case record' }),
    waypoint(3, 'landing_zone', 'LZ 1', { lat: 31.5024843, lon: -110.6752897, description: 'Grass bench, about 150 by 100 m, nearly level', radio_id: 4 }),
    waypoint(4, 'evidence', 'Boot prints', {
        lat: 31.5071259, lon: -110.6693262, description: 'Single set in the wash, heading east', radio_id: 1,
        time: '2025-04-14T08:37:31Z', created_time: '2025-04-14T08:38:41Z',
    }),
    waypoint(5, 'find', 'Helicopter sighting', {
        lat: 31.51, lon: -110.6533, description: 'Heat signature on FLIR, not yet confirmed on the ground',
        note: 'Reported by the Border Patrol helicopter', time: '2025-04-14T08:51:19Z', created_time: '2025-04-14T08:52:19Z',
    }),
    waypoint(6, 'find', 'Subject found', { lat: 31.5100011, lon: -110.653263, description: 'Adult male, conscious, able to walk', radio_id: 1 }),
]

// A board holding these waypoints, whose changes do nothing and answer that they failed
// unless a test gives its own.
export function board(waypoints: Waypoint[], changes: Partial<WaypointsBoard> = {}): WaypointsBoard {
    return {
        waypoints, add: async () => 'Not in this test.', change: async () => 'Not in this test.', remove: async () => 'Not in this test.',
        ...changes,
    }
}
