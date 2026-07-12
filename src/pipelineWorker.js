/**
 * Worker-thread entry point for the server.
 * Imports runPipeline and relays every progress event back to the main thread.
 */
import { workerData, parentPort } from 'worker_threads';
import { runPipeline } from './pipeline.js';

try {
  await runPipeline(workerData, event => parentPort.postMessage(event));
} catch (err) {
  parentPort.postMessage({ type: 'error', message: err.message });
}
