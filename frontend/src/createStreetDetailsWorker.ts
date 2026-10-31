export function createStreetDetailsWorker(): Worker {
  return new Worker(new URL('./streetDetails.worker.ts', import.meta.url));
}
