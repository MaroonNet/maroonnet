type Props = {
    hidden: string[]                          // the layer groups the user has hidden
    setHidden: (hidden: string[]) => void
}

// Checkboxes that hide and show groups of map layers (each layer's metadata.group in the style).
function LayerToggles({ hidden, setHidden }: Props) {
    function toggle(group: string, shown: boolean) {
        setHidden(shown ? hidden.filter((g) => g !== group) : [...hidden, group])
    }

    return (
        <div style={panelStyle}>
            <label>
                <input
                    type="checkbox"
                    checked={!hidden.includes('trails')}
                    onChange={(e) => toggle('trails', e.target.checked)}
                />
                Trails
            </label>
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
