import { createContext, useContext } from 'react'
import { dayNumber } from './missionTime.ts'

// A mission and its sessions, as the backend answers them (backend/mission/files.py).
// Every time is in UTC; missionTime.ts shows it in the mission's time zone.
export type MissionStatus = 'planning' | 'active' | 'paused' | 'ended'

export type SessionFacts = {
    number: number
    status: MissionStatus
    start_time: string | null  // none while the session is in planning
    end_time: string | null    // none until the session is paused or ended
}

// A mission as the list shows it. Its status, session number and times are those of its
// latest session.
export type Mission = {
    id: string
    name: string
    time_zone: string
    status: MissionStatus
    session: number
    start_time: string | null
    end_time: string | null
    sessions: SessionFacts[]  // every session, first to latest
}

// The open mission. asks_to_continue: the backend started and found its session still
// active, so the app asks whether to continue it or end it.
export type OpenMission = Mission & { asks_to_continue: boolean }

export const STATUS_LABELS: Record<MissionStatus, string> = {
    planning: 'Planning', active: 'Active', paused: 'Paused', ended: 'Ended',
}

// "Day 1 · Session 2". The day comes from the dates the sessions started on, in the
// mission's time zone. A mission that has not started has no day yet: "Session 1".
export function dayAndSession(mission: Mission): string {
    if (!mission.start_time) return `Session ${mission.session}`
    const starts = mission.sessions.flatMap((session) => session.start_time ?? [])
    return `Day ${dayNumber(starts, mission.time_zone)} · Session ${mission.session}`
}

// Sends one request to the backend and answers with what it sent back. A refusal is thrown
// as an Error whose message is the backend's own line, such as "No mission is open."
export async function ask<Answer>(address: string, method = 'GET', body?: unknown): Promise<Answer> {
    const response = await fetch(address, {
        method,
        headers: body === undefined ? undefined : { 'content-type': 'application/json' },
        body: body === undefined ? undefined : JSON.stringify(body),
    })
    if (response.status === 204) return null as Answer  // done, with nothing to send back
    const answer = await response.json().catch(() => null)
    if (response.ok) return answer
    // The backend's reason is one line, or a list when the request itself was wrong.
    const detail = answer?.detail
    const reason = typeof detail === 'string' ? detail : Array.isArray(detail) ? detail[0]?.msg : null
    throw new Error(reason ?? `${response.status} ${response.statusText}`)
}

// The backend's mission routes (backend/mission/routes.py). Each one that changes the open
// mission answers with it as it now is.
export const listMissions = () => ask<Mission[]>('/api/missions')
export const loadOpenMission = () => ask<OpenMission | null>('/api/mission')
export const openMission = (id: string) => ask<OpenMission>(`/api/missions/${id}/open`, 'POST')
export const createMission = (name: string, time_zone: string) => ask<OpenMission>('/api/missions', 'POST', { name, time_zone })
export const closeMission = () => ask<null>('/api/mission/close', 'POST')
export const startMission = () => ask<OpenMission>('/api/mission/start', 'POST')
export const endSession = () => ask<OpenMission>('/api/mission/end-session', 'POST')
export const endMission = () => ask<OpenMission>('/api/mission/end', 'POST')
export const resumeSession = () => ask<OpenMission>('/api/mission/resume', 'POST')
export const reopenMission = () => ask<OpenMission>('/api/mission/reopen', 'POST')
export const continueSession = () => ask<OpenMission>('/api/mission/continue', 'POST')
export const startNextSession = (keep_teams: boolean) => ask<OpenMission>('/api/mission/next-session', 'POST', { keep_teams })
export const changeTimeZone = (time_zone: string) => ask<OpenMission>('/api/mission', 'PATCH', { time_zone })

// The board: the open mission, kept in one place that any component can read.
export type MissionBoard = {
    mission: OpenMission | null  // none: no mission is open
    loadFailed: boolean          // the open mission could not be read when the app opened
    // Waits for one of the requests above and puts the mission it answers on the board.
    // The answer is empty when it worked, and the reason when it did not; the board
    // changes only when it worked, so the screen always shows what is saved.
    run: (request: Promise<OpenMission | null>) => Promise<string>
}

// A component drawn with no MissionProvider above it, as in a test of one component, reads
// this board: no mission open, and nothing can be changed.
export const MissionContext = createContext<MissionBoard>({
    mission: null,
    loadFailed: false,
    run: async () => 'There is no mission board.',
})

// What a component calls to read the board.
export function useMission(): MissionBoard {
    return useContext(MissionContext)
}
