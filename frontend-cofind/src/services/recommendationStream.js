// src/services/recommendationStream.js
// Klien untuk /api/recommend-by-preferences/stream.
// Memakai fetch + ReadableStream (bukan EventSource) karena endpoint butuh header
// Authorization dan method POST. Otomatis fallback ke endpoint JSON biasa bila
// browser atau server tidak mendukung streaming.

function parseSseChunk(rawEvent) {
    const lines = String(rawEvent || '').split('\n');
    let eventName = 'message';
    const dataLines = [];

    for (const line of lines) {
        if (line.startsWith(':')) continue;
        if (line.startsWith('event:')) {
            eventName = line.slice(6).trim();
        } else if (line.startsWith('data:')) {
            dataLines.push(line.slice(5).trim());
        }
    }

    if (dataLines.length === 0) return null;
    try {
        return { event: eventName, data: JSON.parse(dataLines.join('\n')) };
    } catch {
        return null;
    }
}

async function requestPlainJson({ apiBase, token, preferences, signal }) {
    const res = await fetch(`${apiBase}/api/recommend-by-preferences`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ preferences }),
        signal,
    });
    let body = null;
    try {
        body = await res.json();
    } catch {
        body = null;
    }
    return { statusCode: res.status, body, streamed: false };
}

/**
 * Jalankan pipeline rekomendasi sambil melaporkan progress tiap tahap.
 * @param {(progress: {stage: string, label?: string, percent?: number}) => void} onProgress
 * @returns {Promise<{statusCode: number, body: object|null, streamed: boolean}>}
 */
export async function streamRecommendations({
    apiBase,
    token,
    preferences,
    onProgress,
    signal,
}) {
    if (typeof window === 'undefined' || !window.ReadableStream || !window.TextDecoder) {
        return requestPlainJson({ apiBase, token, preferences, signal });
    }

    let res;
    try {
        res = await fetch(`${apiBase}/api/recommend-by-preferences/stream`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                Accept: 'text/event-stream',
                Authorization: `Bearer ${token}`,
            },
            body: JSON.stringify({ preferences }),
            signal,
        });
    } catch (err) {
        if (err?.name === 'AbortError') throw err;
        return requestPlainJson({ apiBase, token, preferences, signal });
    }

    const contentType = res.headers.get('content-type') || '';
    if (!res.body || !contentType.includes('text/event-stream')) {
        // Server lama tanpa endpoint stream (404) atau proxy yang mengubah respons.
        if (res.status === 404 || !res.body) {
            return requestPlainJson({ apiBase, token, preferences, signal });
        }
        let body = null;
        try {
            body = await res.json();
        } catch {
            body = null;
        }
        return { statusCode: res.status, body, streamed: false };
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    let result = null;

    try {
        for (;;) {
            const { value, done } = await reader.read();
            if (done) break;
            buffer += decoder.decode(value, { stream: true });

            let separatorIndex = buffer.indexOf('\n\n');
            while (separatorIndex !== -1) {
                const rawEvent = buffer.slice(0, separatorIndex);
                buffer = buffer.slice(separatorIndex + 2);
                const parsed = parseSseChunk(rawEvent);
                if (parsed) {
                    if (parsed.event === 'progress') {
                        onProgress?.(parsed.data);
                    } else if (parsed.event === 'result') {
                        result = {
                            statusCode: parsed.data?.status_code ?? 200,
                            body: parsed.data?.body ?? null,
                            streamed: true,
                        };
                    }
                }
                separatorIndex = buffer.indexOf('\n\n');
            }
        }
    } finally {
        try {
            reader.releaseLock();
        } catch {
            /* stream sudah tertutup */
        }
    }

    if (!result) {
        throw new Error('Koneksi rekomendasi terputus sebelum hasil diterima.');
    }
    return result;
}
