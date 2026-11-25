import type { LogLine, MessageLine, SectorLine } from './log.ts'

// A made-up log for the message tests, shaped like Arizona07's. Arizona is seven hours
// behind UTC, so 03:50 UTC is 8:50 pm.

export const ASSIGNED: SectorLine = {
    kind: 'sector', id: 1, time: '2025-04-14T03:50:00Z', event: 'assigned',
    sector_id: 1, sector_name: 'S1', group_id: 1, partial: false,
}
export const TO_ONE: MessageLine = {
    kind: 'message', id: 1, time: '2025-04-14T06:24:00Z', type: 'instruction', direction: 'out',
    addressing: 'direct', text: 'Radio 4: find a landing zone.',
    radios: [{ radio_id: 4, ack_time: '2025-04-14T06:24:13Z' }],
}
export const COMPLETED: SectorLine = {
    kind: 'sector', id: 3, time: '2025-04-14T07:24:46Z', event: 'completed',
    sector_id: 3, sector_name: 'S3', group_id: 2, partial: false,
}
export const FROM_ONE: MessageLine = {
    kind: 'message', id: 2, time: '2025-04-14T07:33:23Z', type: 'evidence', direction: 'in',
    addressing: 'direct', text: 'Landing zone marked.',
    radios: [{ radio_id: 4, ack_time: null }],
}
export const TO_TWO: MessageLine = {
    kind: 'message', id: 5, time: '2025-04-14T08:51:19Z', type: 'instruction', direction: 'out',
    addressing: 'multicast', text: 'Move to the helicopter point.',
    radios: [{ radio_id: 1, ack_time: '2025-04-14T08:51:29Z' }, { radio_id: 2, ack_time: null }],
}
export const FOUND: MessageLine = {
    kind: 'message', id: 7, time: '2025-04-14T09:34:53Z', type: 'found', direction: 'in',
    addressing: 'direct', text: 'Subject located.',
    radios: [{ radio_id: 1, ack_time: null }],
}
export const RELEASED: SectorLine = {
    kind: 'sector', id: 5, time: '2025-04-14T09:37:58Z', event: 'released',
    sector_id: 4, sector_name: 'S4', group_id: 3, partial: true,
}
export const TO_ALL: MessageLine = {
    kind: 'message', id: 8, time: '2025-04-14T09:38:23Z', type: 'instruction', direction: 'out',
    addressing: 'broadcast', text: 'Subject found. All teams return to CP.',
    radios: [1, 2, 3].map((radio_id) => ({ radio_id, ack_time: `2025-04-14T09:38:3${radio_id}Z` })),
}

// Oldest first, as the backend answers them.
export const LINES: LogLine[] = [ASSIGNED, TO_ONE, COMPLETED, FROM_ONE, TO_TWO, FOUND, RELEASED, TO_ALL]
