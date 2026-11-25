import { ask } from '../mission/mission.ts'

// A line of the Communication Log, as the backend answers it (backend/messages/log.py).
// Every time is in UTC.

// One radio of a message, and when it acknowledged.
export type Receipt = {
    radio_id: number
    ack_time: string | null     // none: not acknowledged. A message from a radio has none.
}

// One send. A send to several radios is one line that lists each of them.
export type MessageLine = {
    kind: 'message'
    id: number
    time: string
    type: string                // "evidence", "found", "instruction", "out_of_sector" or "assignment"
    direction: 'in' | 'out'     // in: from a radio. out: from the command post.
    addressing: 'direct' | 'multicast' | 'broadcast'
    text: string
    radios: Receipt[]           // by radio: the one it came from, or each one it went to
}

// A sector given to a group, or that ending. It is read from the sector's history; no
// message was sent for it.
export type SectorLine = {
    kind: 'sector'
    id: number
    time: string
    event: 'assigned' | 'completed' | 'released'
    sector_id: number
    sector_name: string
    group_id: number
    partial: boolean            // a released line only: the sector is searched in part
}

export type LogLine = MessageLine | SectorLine

// Every line of the open session, oldest first.
export const loadLog = () => ask<LogLine[]>('/api/mission/log')
