import { IconChevronDown, IconChevronRight } from '@tabler/icons-react'
import { useState } from 'react'
import type { LayerGroup } from '../map/styleChoices'
import { MISSION_LAYERS, type LayerChoice, type MissionLayerChoices, type MissionLayerId } from './missionLayers.ts'

type Props = {
    groups: LayerGroup[]
    hidden: string[]                          // the layer groups the user has hidden
    setHidden: (hidden: string[]) => void
    missionLayers: MissionLayerChoices        // how each mission layer is drawn
    setMissionLayers: (missionLayers: MissionLayerChoices) => void
}

// The contents of the Layers panel. First the mission layers, which the app draws over the
// map: each has a checkbox, and an arrow that opens its opacity slider. Then the basemap:
// checkboxes that hide and show groups of map layers (each layer's metadata.group in the
// style), Trails among them.
function LayersPanel({ groups, hidden, setHidden, missionLayers, setMissionLayers }: Props) {
    const [openSlider, setOpenSlider] = useState<MissionLayerId | null>(null)  // one slider is open at a time
    const change = (id: MissionLayerId, choice: Partial<LayerChoice>) =>
        setMissionLayers({ ...missionLayers, [id]: { ...missionLayers[id], ...choice } })
    return (
        <div className="pt-1.5 pb-2.5">
            <Heading>Mission</Heading>
            {MISSION_LAYERS.map(({ id, label }) => {
                const { shown, opacity } = missionLayers[id]
                const open = openSlider === id
                const percent = Math.round(opacity * 100)
                return (
                    <div key={id}>
                        <div className="flex items-center">
                            <div className="min-w-0 flex-1">
                                <CheckRow label={label} checked={shown} onChange={(checked) => change(id, { shown: checked })} />
                            </div>
                            <button
                                type="button"
                                aria-label={`Opacity of ${label}`}
                                title="Opacity"
                                aria-expanded={open}
                                onClick={() => setOpenSlider(open ? null : id)}
                                className="mr-2.5 flex size-5 flex-none cursor-pointer items-center justify-center rounded-control hover:bg-strip"
                            >
                                {open ? <IconChevronDown size={14} stroke={1.75} aria-hidden /> : <IconChevronRight size={14} stroke={1.75} aria-hidden />}
                            </button>
                        </div>
                        {open && (
                            <div className="flex items-center gap-2.5 pt-0.5 pr-4 pb-1.5 pl-10">
                                <span className="font-mono text-label tracking-widest text-muted uppercase">Opacity</span>
                                <input
                                    type="range"
                                    min={0}
                                    max={100}
                                    step={5}
                                    value={percent}
                                    aria-label={`Opacity of ${label}`}
                                    onChange={(e) => change(id, { opacity: Number(e.target.value) / 100 })}
                                    className="min-w-0 flex-1 accent-ink"
                                />
                                <span className="w-10 flex-none text-right font-mono text-figure">{percent}%</span>
                            </div>
                        )}
                    </div>
                )
            })}
            <Heading>Basemap</Heading>
            {groups.map((group) => (
                <CheckRow
                    key={group.id}
                    label={group.label}
                    checked={!hidden.includes(group.id)}
                    onChange={(checked) => setHidden(withOrWithout(hidden, group.id, !checked))}
                />
            ))}
        </div>
    )
}

function Heading({ children }: { children: string }) {
    return <h3 className="px-4 pt-3 pb-1 font-mono text-label tracking-widest text-muted uppercase">{children}</h3>
}

// One row: a checkbox and its label. Pressing anywhere on the row ticks it.
function CheckRow({ label, checked, onChange }: { label: string, checked: boolean, onChange: (checked: boolean) => void }) {
    return (
        <label className="flex cursor-pointer items-center gap-2 py-1 pr-2.5 pl-4 font-medium">
            <input
                type="checkbox"
                checked={checked}
                onChange={(e) => onChange(e.target.checked)}
                className="size-3.5 flex-none accent-ink"
            />
            <span>{label}</span>
        </label>
    )
}

// The list with the item added (include) or taken out.
function withOrWithout(list: string[], item: string, include: boolean): string[] {
    return include ? [...list, item] : list.filter((x) => x !== item)
}

export default LayersPanel
