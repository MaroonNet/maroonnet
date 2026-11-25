import { IconCheck } from '@tabler/icons-react'
import { useSetupSteps, type SetupStep } from './setupSteps.ts'

// How a step is said to a screen reader, after its name.
const said = (step: SetupStep) => step.done ? 'done' : step.red ? 'maps missing' : 'not done'

// The setup bar, beside the toolbar while the open mission is in planning. It is a
// checklist and not a row of buttons: each step is done with its own tool or panel, in any
// order, and shows a tick here once the mission's data says it is done. It goes away when
// the mission starts.
function SetupBar() {
    const steps = useSetupSteps()
    if (!steps) return null
    return (
        <div className="flex h-10 items-center gap-3.5 rounded-box border border-ink bg-panel px-3.5 whitespace-nowrap shadow-[0_1px_6px_rgb(32_30_24/0.25)]">
            {/* The list carries the name, so the word is not read out twice. */}
            <span aria-hidden className="font-mono text-label tracking-widest text-muted uppercase">Setup</span>
            <ol aria-label="Setup" className="flex items-center gap-3.5">
                {steps.map((step, index) => (
                    <li
                        key={step.id}
                        aria-label={`${step.label}: ${said(step)}`}
                        className={`flex items-center gap-1.5 ${step.done ? '' : step.red ? 'text-red' : 'text-muted'}`}
                    >
                        <span className="flex size-4.5 items-center justify-center rounded-full border border-current font-mono text-label">
                            {step.done ? <IconCheck size={12} stroke={2.5} aria-hidden /> : index + 1}
                        </span>
                        {step.label}
                    </li>
                ))}
            </ol>
        </div>
    )
}

export default SetupBar
