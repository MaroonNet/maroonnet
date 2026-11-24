import { useEffect, useState, type ReactNode } from 'react'
import { sendError } from '../diagnostics/errorLog.ts'
import { loadSettings, saveSettings, SettingsContext, STARTING_SETTINGS, type Settings } from './settings.ts'

// Puts the settings board above the whole app. It asks the backend for the settings once,
// when the page opens, and draws nothing until they arrive, so no number on screen is drawn
// in one unit and then switched to another.
function SettingsProvider({ children }: { children: ReactNode }) {
    const [settings, setSettings] = useState<Settings | null>(null)  // null: still on their way
    const [loadFailed, setLoadFailed] = useState(false)

    // If the settings cannot be read, the app carries on with the starting values. It never
    // refuses to start over its settings.
    useEffect(() => {
        loadSettings().then(setSettings).catch((error) => {
            sendError('settings', error)
            setLoadFailed(true)
            setSettings(STARTING_SETTINGS)
        })
    }, [])

    // The board changes only after the backend has saved the change, so the screen always
    // shows what is saved. The answer holds every saved setting, so after it the board is
    // right even if the first read had failed.
    async function change(changes: Partial<Settings>): Promise<boolean> {
        try {
            setSettings(await saveSettings(changes))
            setLoadFailed(false)
            return true
        } catch (error) {
            sendError('settings', error)
            return false
        }
    }

    if (!settings) return null
    return (
        <SettingsContext value={{ settings, loadFailed, change }}>
            {children}
        </SettingsContext>
    )
}

export default SettingsProvider
