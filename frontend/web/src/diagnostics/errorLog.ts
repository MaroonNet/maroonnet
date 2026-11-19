// Sends the page's errors to the backend's terminal (POST /api/client-log).
// Imported first in main.tsx, so it is listening before any other code runs.

// The kinds of error the page reports. The backend prints the kind first on each line.
type ErrorKind = 'error' | 'rejection' | 'map' | 'style'

// error is whatever was caught. It is sent as its text plus, for an Error, its stack trace (the
// chain of calls that led to it). Chrome's stack trace starts with the text; Safari's does not.
export function sendError(kind: ErrorKind, error: unknown) {
    const stack = error instanceof Error ? error.stack ?? '' : ''
    const detail = stack.startsWith(String(error)) ? stack : `${error}\n${stack}`.trimEnd()
    fetch('/api/client-log', {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ kind, detail }),
    }).catch(() => {})  // the backend is unreachable, so there is nowhere to send it
}

// An error that no code caught.
window.addEventListener('error', (e) => sendError('error', e.error ?? e.message))

// A rejection: a promise (a placeholder for an answer still on its way) whose answer came back
// as a failure, and no code handled it.
window.addEventListener('unhandledrejection', (e) => sendError('rejection', e.reason))
