// Basic headless smoke test to ensure key modules import without runtime exceptions.
import { JSDOM } from 'jsdom';

// Create a minimal DOM environment
const dom = new JSDOM('<!doctype html><html><head></head><body><div id="root"></div></body></html>', {
  url: 'http://localhost/',
});
global.window = dom.window;
global.document = dom.window.document;
// Omit assigning navigator (read-only in newer Node versions).
global.HTMLElement = dom.window.HTMLElement;
global.CustomEvent = dom.window.CustomEvent;

function log(step, ok, extra='') {
  const status = ok ? '✅' : '❌';
  console.log(`${status} ${step}${extra ? ' - ' + extra : ''}`);
}

try {
  // Dynamic imports so failures are caught individually
  const react = await import('react');
  log('Import react', !!react);
  const three = await import('three');
  log('Import three', !!three);
  const roslib = await import('roslib');
  log('Import roslib', !!roslib);
  // NOTE: Internal TS modules are skipped (not transpiled yet). This checks core external libs presence.

  console.log('\nSmoke test finished. If all steps show ✅, imports are healthy.');
  process.exit(0);
} catch (err) {
  console.error('Smoke test failed early:', err);
  process.exit(1);
}