// Every request carries its project. Switching another tab cannot redirect saves.
export function createApi(session, fetcher = (...args) => fetch(...args)) {
  return async function request(path, {body, signal, projectId, timeout = 160000} = {}) {
    const context = session(), controller = new AbortController();
    let timedOut = false;
    const abort = () => controller.abort();
    if (signal?.aborted) controller.abort();
    signal?.addEventListener('abort', abort, {once: true});
    const timer = setTimeout(() => { timedOut = true; controller.abort(); }, timeout);
    const headers = {};
    const target = projectId === undefined ? context.workspaceId : projectId;
    if (target) headers['X-Review-Project'] = target;
    if (body !== undefined) Object.assign(headers, {'Content-Type': 'application/json', 'X-Review-Token': context.token});
    try {
      const response = await fetcher(path, {method: body === undefined ? 'GET' : 'POST', headers,
        ...(body === undefined ? {} : {body: JSON.stringify(body)}), signal: controller.signal});
      let data;
      try { data = await response.json(); }
      catch { throw new Error('Der lokale Server lieferte keine gültige Antwort. Bitte Server und Seite neu starten.'); }
      if (controller.signal.aborted) throw new DOMException('Abgebrochen', 'AbortError');
      if (!response.ok) throw new Error(data.error || `Die Anfrage ist fehlgeschlagen (HTTP ${response.status}).`);
      return data;
    } catch (error) {
      if (timedOut) throw new Error('Die Anfrage dauert zu lange. Bitte erneut versuchen; bisherige Prüfungen bleiben erhalten.');
      if (controller.signal.aborted) throw new DOMException('Abgebrochen', 'AbortError');
      if (error instanceof TypeError) throw new Error('Der lokale Server ist nicht erreichbar. Bitte den Server prüfen und erneut versuchen.');
      throw error;
    } finally {
      clearTimeout(timer);
      signal?.removeEventListener('abort', abort);
    }
  };
}

export function wait(ms, signal) {
  return new Promise((resolve, reject) => {
    if (signal.aborted) { reject(new DOMException('Abgebrochen', 'AbortError')); return; }
    const abort = () => { clearTimeout(timer); reject(new DOMException('Abgebrochen', 'AbortError')); };
    const timer = setTimeout(() => { signal.removeEventListener('abort', abort); resolve(); }, ms);
    signal.addEventListener('abort', abort, {once: true});
  });
}
