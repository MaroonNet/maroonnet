import type { FilterSpecification } from 'maplibre-gl'

export type LayerGroup = { id: string, label: string }  // as listed in the style's metadata.groups
export type TrailUse = { id: string, label: string, filter: FilterSpecification }  // metadata.trail_uses

type Props = {
    groups: LayerGroup[]
    hidden: string[]                          // the layer groups the user has hidden
    setHidden: (hidden: string[]) => void
    trailUses: TrailUse[]
    pickedUses: string[]                      // the trail uses ticked; none ticked: all trails
    setPickedUses: (pickedUses: string[]) => void
}

// Checkboxes that hide and show groups of map layers (each layer's metadata.group in the style),
// and checkboxes that narrow the trails to the ones open to any ticked use.
function LayerToggles({ groups, hidden, setHidden, trailUses, pickedUses, setPickedUses }: Props) {
    return (
        <div style={panelStyle}>
            {groups.map((group) => (
                <div key={group.id}>
                    <label style={{ display: 'block' }}>
                        <input
                            type="checkbox"
                            checked={!hidden.includes(group.id)}
                            onChange={(e) => setHidden(withOrWithout(hidden, group.id, !e.target.checked))}
                        />
                        {group.label}
                    </label>
                    {group.id === 'trails' && trailUses.map((use) => (
                        <label key={use.id} style={{ display: 'block', marginLeft: 20 }}>
                            <input
                                type="checkbox"
                                checked={pickedUses.includes(use.id)}
                                onChange={(e) => setPickedUses(withOrWithout(pickedUses, use.id, e.target.checked))}
                            />
                            {use.label}
                        </label>
                    ))}
                </div>
            ))}
        </div>
    )
}

// The list with the item added (include) or taken out.
function withOrWithout(list: string[], item: string, include: boolean): string[] {
    return include ? [...list, item] : list.filter((x) => x !== item)
}

const panelStyle = {
    position: 'absolute',
    top: 10,
    left: 10,
    padding: '6px 10px',
    background: 'rgba(255, 255, 255, 0.9)',
    borderRadius: 4,
    font: '13px system-ui, sans-serif',
} as const

export default LayerToggles
