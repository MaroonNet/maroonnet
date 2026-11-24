import type { LayerGroup, TrailUse } from '../map/styleChoices'

type Props = {
    groups: LayerGroup[]
    hidden: string[]                          // the layer groups the user has hidden
    setHidden: (hidden: string[]) => void
    trailUses: TrailUse[]
    pickedUses: string[]                      // the trail uses ticked; none ticked: all trails
    setPickedUses: (pickedUses: string[]) => void
}

// The contents of the Layers panel. Checkboxes that hide and show groups of map layers (each
// layer's metadata.group in the style), and under Trails, checkboxes that narrow the trails to
// the ones open to any ticked use.
function LayersPanel({ groups, hidden, setHidden, trailUses, pickedUses, setPickedUses }: Props) {
    return (
        <div className="pt-1.5 pb-2.5">
            <h3 className="px-4 pt-3 pb-1 font-mono text-label tracking-widest text-muted uppercase">Basemap</h3>
            {groups.map((group) => (
                <div key={group.id}>
                    <CheckRow
                        label={group.label}
                        checked={!hidden.includes(group.id)}
                        onChange={(checked) => setHidden(withOrWithout(hidden, group.id, !checked))}
                    />
                    {group.id === 'trails' && (
                        <div className="pb-1 pl-6">
                            {trailUses.map((use) => (
                                <CheckRow
                                    key={use.id}
                                    label={use.label}
                                    checked={pickedUses.includes(use.id)}
                                    onChange={(checked) => setPickedUses(withOrWithout(pickedUses, use.id, checked))}
                                />
                            ))}
                        </div>
                    )}
                </div>
            ))}
        </div>
    )
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
