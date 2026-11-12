// Sends the page's errors to the backend's terminal (POST /api/client-log).
// Imported first in main.tsx, so it is listening before any other code runs.

export function sendError(kind: string, detail: unknown) {
    fetch('/api/client-log', {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ kind, detail: String(detail) }),
    }).catch(() => {})  // the backend is unreachable, so there is nowhere to send it
}

// An error that no code caught.
window.addEventListener('error', (e) => sendError('error', e.error?.stack ?? e.message))

// A rejection: a failed promise (an answer that was waited for and never came) that no code handled.
window.addEventListener('unhandledrejection', (e) => sendError('rejection', e.reason?.stack ?? e.reason))
