import { useState } from 'react'
import { useSettings, type Units } from './settings.ts'

const UNIT_CHOICES: { value: Units, label: string }[] = [
    { value: 'imperial', label: 'Miles and feet' },
    { value: 'metric', label: 'Kilometers and meters' },
]

// The contents of the Settings panel.
function SettingsPanel() {
    const { settings, loadFailed, change } = useSettings()
    const [saveFailed, setSaveFailed] = useState(false)  // the last change could not be saved

    async function pickUnits(units: Units) {
        const saved = await change({ units })
        setSaveFailed(!saved)
    }

    return (
        <div className="pt-1.5 pb-2.5">
            {loadFailed && (
                <p className="px-4 pt-3 font-medium text-muted">
                    The settings could not be loaded, so the starting values are shown.
                </p>
            )}
            <h3 className="px-4 pt-3 pb-1 font-mono text-label tracking-widest text-muted uppercase">Units</h3>
            {UNIT_CHOICES.map((choice) => (
                <label key={choice.value} className="flex cursor-pointer items-center gap-2 py-1 pr-2.5 pl-4 font-medium">
                    <input
                        type="radio"
                        name="units"
                        checked={settings.units === choice.value}
                        onChange={() => pickUnits(choice.value)}
                        className="size-3.5 flex-none accent-ink"
                    />
                    <span>{choice.label}</span>
                </label>
            ))}
            {/* role="alert" has a screen reader read the line out when it appears. */}
            {saveFailed && <p role="alert" className="px-4 pt-1 font-medium text-red">The change could not be saved.</p>}
        </div>
    )
}

export default SettingsPanel
