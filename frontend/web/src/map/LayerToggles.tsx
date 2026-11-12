export type LayerGroup = { id: string, label: string }  // as listed in the style's metadata.groups

type Props = {
    groups: LayerGroup[]
    hidden: string[]                          // the layer groups the user has hidden
    setHidden: (hidden: string[]) => void
}

// Checkboxes that hide and show groups of map layers (each layer's metadata.group in the style).
function LayerToggles({ groups, hidden, setHidden }: Props) {
    function toggle(group: string, shown: boolean) {
        setHidden(shown ? hidden.filter((g) => g !== group) : [...hidden, group])
    }

    return (
        <div style={panelStyle}>
            {groups.map((group) => (
                <label key={group.id} style={{ display: 'block' }}>
                    <input
                        type="checkbox"
                        checked={!hidden.includes(group.id)}
                        onChange={(e) => toggle(group.id, e.target.checked)}
                    />
                    {group.label}
                </label>
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
