import type { FilterSpecification } from 'maplibre-gl'

export type LayerGroup = { id: string, label: string }  // as listed in the style's metadata.groups
export type TrailUse = { id: string, label: string, filter: FilterSpecification }  // metadata.trail_uses

type Props = {
    groups: LayerGroup[]
    hidden: string[]                          // the layer groups the user has hidden
    setHidden: (hidden: string[]) => void
    trailUses: TrailUse[]
    trailUse: string | null                   // the use the trails are narrowed to; null: all trails
    setTrailUse: (trailUse: string | null) => void
}

// Checkboxes that hide and show groups of map layers (each layer's metadata.group in the style),
// and a choice that narrows the trails to one use.
function LayerToggles({ groups, hidden, setHidden, trailUses, trailUse, setTrailUse }: Props) {
    function toggle(group: string, shown: boolean) {
        setHidden(shown ? hidden.filter((g) => g !== group) : [...hidden, group])
    }

    return (
        <div style={panelStyle}>
            {groups.map((group) => (
                <div key={group.id}>
                    <label style={{ display: 'block' }}>
                        <input
                            type="checkbox"
                            checked={!hidden.includes(group.id)}
                            onChange={(e) => toggle(group.id, e.target.checked)}
                        />
                        {group.label}
                    </label>
                    {group.id === 'trails' && trailUses.map((use) => (
                        <label key={use.id} style={{ display: 'block', marginLeft: 20 }}>
                            <input
                                type="checkbox"
                                checked={trailUse === use.id}
                                onChange={(e) => setTrailUse(e.target.checked ? use.id : null)}
                            />
                            {use.label}
                        </label>
                    ))}
                </div>
            ))}
        </div>
    )
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
