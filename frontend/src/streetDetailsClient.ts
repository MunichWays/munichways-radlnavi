import { createStreetDetailsWorker } from './createStreetDetailsWorker';
import { StreetManifest, StreetNetworkMode, StreetProperties, StreetSearchResult, streetDetailGroup } from './streetDetails';

const aborted = () => new DOMException('Abgebrochen', 'AbortError');
type Pending = { resolve: (result: StreetSearchResult) => void; reject: (error: Error) => void; cleanup: () => void };

export class StreetDetailsClient {
  private worker?: Worker;
  private sequence = 0;
  private pending = new Map<number, Pending>();
  private groups = new Map<string, Record<string, StreetProperties>>();

  search(lat: number, lng: number, zoom: number, signal: AbortSignal, mode: StreetNetworkMode = 'all'): Promise<StreetSearchResult> {
    if (signal.aborted) return Promise.reject(aborted());
    return new Promise((resolve, reject) => {
      if (!this.worker) {
        this.worker = createStreetDetailsWorker();
        this.worker.onmessage = event => {
          const task = this.pending.get(event.data.id);
          if (!task) return;
          this.pending.delete(event.data.id); task.cleanup();
          if (event.data.error) task.reject(new Error(event.data.error));
          else task.resolve(event.data.result);
        };
        this.worker.onerror = () => this.resetWorker(new Error('Die Streckensuche konnte nicht gestartet werden. Bitte erneut versuchen.'));
      }
      const id = ++this.sequence;
      const cancel = () => {
        const task = this.pending.get(id);
        if (task) { this.pending.delete(id); task.cleanup(); task.reject(aborted()); }
      };
      const timer = setTimeout(() => this.resetWorker(new Error('Die Streckensuche hat zu lange gedauert. Bitte erneut versuchen.')), 100000);
      this.pending.set(id, { resolve, reject, cleanup: () => { clearTimeout(timer); signal.removeEventListener('abort', cancel); } });
      signal.addEventListener('abort', cancel, { once: true });
      try { this.worker.postMessage({ id, lat, lng, zoom, mode }); }
      catch { this.resetWorker(new Error('Die Streckensuche konnte nicht gestartet werden. Bitte erneut versuchen.')); }
    });
  }

  async details(manifest: StreetManifest, id: string, signal: AbortSignal): Promise<StreetProperties> {
    if (signal.aborted) throw aborted();
    const group = streetDetailGroup(id);
    const key = `${manifest.snapshot}/${group}`;
    let entries = this.groups.get(key);
    if (!entries) {
      const controller = new AbortController();
      const cancel = () => controller.abort();
      signal.addEventListener('abort', cancel, { once: true });
      const timeout = setTimeout(cancel, 30000);
      try {
        const response = await fetch(`/street-details/${manifest.snapshot}/details/${group}.json`, { signal: controller.signal });
        if (!response.ok || !response.headers.get('content-type')?.includes('application/json')) {
          throw new Error('Die Streckendetails sind nicht verfügbar. Bitte erneut versuchen; bei einem neuen Datenstand die Seite neu laden.');
        }
        const body = await response.json();
        if (!body || typeof body !== 'object' || Array.isArray(body)) throw new Error('Ungültige Streckendetails.');
        entries = body;
        if (signal.aborted) throw aborted();
        if (this.groups.size >= 8) this.groups.delete(this.groups.keys().next().value);
        this.groups.set(key, body);
      } catch (error) {
        if (signal.aborted) throw aborted();
        if (controller.signal.aborted) throw new Error('Das Laden der Streckendetails hat zu lange gedauert. Bitte erneut versuchen.');
        throw error;
      } finally { clearTimeout(timeout); signal.removeEventListener('abort', cancel); }
    }
    const properties = entries?.[id];
    if (!properties || String(properties.osm_id) !== id.slice(4) || Object.values(properties).some(v => v !== null && typeof v !== 'string' && typeof v !== 'number')) {
      this.groups.delete(key);
      throw new Error('Für diese Strecke fehlen gültige Details.');
    }
    return properties;
  }

  private resetWorker(error: Error) {
    this.worker?.terminate(); this.worker = undefined;
    this.pending.forEach(task => { task.cleanup(); task.reject(error); });
    this.pending.clear();
  }
  dispose() { this.resetWorker(aborted()); this.groups.clear(); }
}
