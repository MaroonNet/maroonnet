type Props = {
    text: string        // what to do next
    figure?: string     // a running figure, such as the size of the shape being drawn
}

// The line under the toolbar while a tool is in use. role="status" has a screen reader read
// the line out when it changes.
function HintLine({ text, figure }: Props) {
    return (
        <div role="status" className="rounded-control bg-ink px-3 py-1.5 text-panel">
            {figure && <span className="mr-2 font-mono opacity-70">{figure}</span>}
            {text}
        </div>
    )
}

export default HintLine
