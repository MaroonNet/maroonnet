import { useState, type FormEvent } from 'react'
import Button from '../frame/Button.tsx'
import { FIELD } from '../mission/MissionList.tsx'
import type { PersonDetails } from './people.ts'

const NO_ONE: PersonDetails = { first_name: '', middle_initial: null, last_name: '', phone: null }

type Props = {
    start?: PersonDetails       // the person being edited; left out for someone new
    note?: string               // a line under the boxes saying what the button does
    submitLabel: string
    // Sends what was typed. Answers with nothing when it worked, and the reason when it did not.
    onSubmit: (details: PersonDetails) => Promise<string>
    onCancel: () => void
}

// The boxes for a roster person: first name, middle initial, last name and phone. The
// button is greyed until there is a first and a last name. The backend drops the spaces
// around each and makes the initial a capital.
function PersonForm({ start = NO_ONE, note, submitLabel, onSubmit, onCancel }: Props) {
    const [first, setFirst] = useState(start.first_name)
    const [initial, setInitial] = useState(start.middle_initial ?? '')
    const [last, setLast] = useState(start.last_name)
    const [phone, setPhone] = useState(start.phone ?? '')
    const [busy, setBusy] = useState(false)     // the request is on its way
    const [failure, setFailure] = useState('')  // why it did not work

    async function submit(event: FormEvent) {
        event.preventDefault()  // the browser would otherwise reload the page
        setBusy(true)
        const reason = await onSubmit({ first_name: first, middle_initial: initial || null, last_name: last, phone: phone || null })
        // When it worked the form has been taken off the screen, and there is nothing to set.
        if (reason) {
            setBusy(false)
            setFailure(reason)
        }
    }

    return (
        <form onSubmit={submit} className="flex flex-col gap-2 px-4 pt-3">
            <div className="flex gap-2">
                <label className="flex min-w-0 flex-1 flex-col gap-1 font-medium">
                    First name
                    <input value={first} onChange={(event) => setFirst(event.target.value)} maxLength={40} className={FIELD} />
                </label>
                <label className="flex w-24 flex-none flex-col gap-1 font-medium">
                    Middle initial
                    <input value={initial} onChange={(event) => setInitial(event.target.value)} maxLength={1} className={FIELD} />
                </label>
            </div>
            <label className="flex flex-col gap-1 font-medium">
                Last name
                <input value={last} onChange={(event) => setLast(event.target.value)} maxLength={40} className={FIELD} />
            </label>
            <label className="flex flex-col gap-1 font-medium">
                Phone number
                <input type="tel" value={phone} onChange={(event) => setPhone(event.target.value)} maxLength={20} placeholder="Optional" className={FIELD} />
            </label>
            {note && <p className="font-medium text-muted">{note}</p>}
            {/* role="alert" has a screen reader read the line out when it appears. */}
            {failure && <p role="alert" className="font-medium text-red">{failure}</p>}
            <div className="flex gap-2 pt-1">
                <Button type="submit" look="dark" disabled={busy || !first.trim() || !last.trim()}>{submitLabel}</Button>
                <Button disabled={busy} onClick={onCancel}>Cancel</Button>
            </div>
        </form>
    )
}

export default PersonForm
