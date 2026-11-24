import { createContext, useContext } from 'react'

// The settings, as the backend saves them (backend/settings/settings_file.py).
export type Units = 'imperial' | 'metric'  // miles and feet, or kilometers and meters
export type Settings = { units: Units }

// What every setting is until the user changes it. The backend has the same values.
export const STARTING_SETTINGS: Settings = { units: 'imperial' }

// Asks the backend for the saved settings. A failure is thrown, for the caller to handle.
export async function loadSettings(): Promise<Settings> {
    const response = await fetch('/api/settings')
    if (!response.ok) throw new Error(`${response.status} ${response.statusText}`)  // an answer, but an error
    return response.json()
}

// Sends the backend the settings that changed, and only those. It answers with all the
// settings as they are now saved. A failure is thrown, for the caller to handle.
export async function saveSettings(changes: Partial<Settings>): Promise<Settings> {
    const response = await fetch('/api/settings', {
        method: 'PATCH',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify(changes),
    })
    if (!response.ok) throw new Error(`${response.status} ${response.statusText}`)
    return response.json()
}

// The board: the settings, kept in one place that any component can read.
export type SettingsBoard = {
    settings: Settings
    loadFailed: boolean  // the settings could not be read, so these are the starting values
    // Saves the named settings. The answer says whether the backend saved them; the
    // settings on the board change only when it did.
    change: (changes: Partial<Settings>) => Promise<boolean>
}

// A component drawn with no SettingsProvider above it, as in a test of one component, reads
// this board: the starting values, which cannot be changed.
export const SettingsContext = createContext<SettingsBoard>({
    settings: STARTING_SETTINGS,
    loadFailed: false,
    change: async () => false,
})

// What a component calls to read the board.
export function useSettings(): SettingsBoard {
    return useContext(SettingsContext)
}
