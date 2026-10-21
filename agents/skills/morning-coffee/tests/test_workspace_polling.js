const assert = require('node:assert/strict');
const {test} = require('node:test');
const {mount} = require('../assets/workspace.js');

const settle = () => new Promise(resolve => setImmediate(resolve));

function fixture({hidden = false, pending = false, deferred = false} = {}) {
  const state = {version: 1, date: '2026-10-21', timezone: 'America/Toronto',
    bridge_configured: true, refresh: pending ? {status: 'pending'} : null};
  const nodes = new Map(), events = new Map(), timers = new Map(), requests = [];
  let sequence = 0, resolveResponse;
  const node = selector => {
    if (!nodes.has(selector)) nodes.set(selector, {textContent: '', setAttribute() {}, addEventListener() {}});
    return nodes.get(selector);
  };
  node('.workspace-interaction-data').textContent = JSON.stringify({status_endpoint: '/workspace/status', token: 'fixture'});
  node('.workspace-state-data').textContent = JSON.stringify(state);
  const response = workspace => ({ok: true, json: async () => ({ok: true, workspace})});
  const view = {
    fetch: async url => {
      requests.push(url);
      return deferred ? new Promise(resolve => {resolveResponse = resolve;}) : response(state);
    },
    clearTimeout: id => timers.delete(id),
    setTimeout: (fn, ms) => {const id = ++sequence; timers.set(id, {fn, ms}); return id;},
    addEventListener: (name, fn) => events.set(name, fn),
  };
  const doc = {hidden, defaultView: view,
    querySelector: selector => selector === '#workspace-controls' ? {querySelector: node} : null,
    addEventListener: (name, fn) => events.set(name, fn)};
  mount(doc);
  return {doc, events, timers, requests,
    respond: workspace => resolveResponse(response(workspace)), state,
    visibility: hidden => {doc.hidden = hidden; events.get('visibilitychange')();}};
}

test('a report opened in the background waits until visible', async () => {
  const f = fixture({hidden: true});
  await settle();
  assert.equal(f.requests.length, 0);
  assert.equal(f.timers.size, 0);
  f.visibility(false);
  await settle();
  assert.deepEqual(f.requests, ['/workspace/status']);
  assert.deepEqual([...f.timers.values()].map(timer => timer.ms), [8000]);
});

test('hiding clears the timer and returning checks immediately without duplicate timers', async () => {
  const f = fixture();
  await settle();
  const staleTimer = [...f.timers.values()][0];
  f.visibility(true);
  assert.equal(f.timers.size, 0);
  await staleTimer.fn();
  assert.equal(f.requests.length, 1);
  f.visibility(false);
  f.visibility(false);
  await settle();
  assert.equal(f.requests.length, 2);
  assert.equal(f.timers.size, 1);
});

test('hiding during a status request skips the report fetch and further polling', async () => {
  const f = fixture({deferred: true});
  f.visibility(true);
  f.respond({...f.state, version: 2});
  await settle();
  assert.deepEqual(f.requests, ['/workspace/status']);
  assert.equal(f.timers.size, 0);
});

test('visible refresh polling retains the one-second cadence', async () => {
  const f = fixture({pending: true});
  await settle();
  assert.deepEqual([...f.timers.values()].map(timer => timer.ms), [1000]);
  f.visibility(true);
  assert.equal(f.timers.size, 0);
});

test('pagehide prevents a late response from restarting polling', async () => {
  const f = fixture({deferred: true});
  f.events.get('pagehide')();
  f.respond(f.state);
  await settle();
  assert.equal(f.timers.size, 0);
});

test('returning from the back-forward cache resumes polling once', async () => {
  const f = fixture();
  await settle();
  f.events.get('pagehide')({persisted: true});
  assert.equal(f.timers.size, 0);
  f.events.get('pageshow')({persisted: true});
  f.events.get('pageshow')({persisted: true});
  await settle();
  assert.equal(f.requests.length, 2);
  assert.equal(f.timers.size, 1);
});

test('restoring while a status request is in flight keeps a single poll loop', async () => {
  const f = fixture({deferred: true});
  f.events.get('pagehide')({persisted: true});
  f.events.get('pageshow')({persisted: true});
  f.respond(f.state);
  await settle();
  assert.deepEqual(f.requests, ['/workspace/status']);
  assert.equal(f.timers.size, 1);
  const next = [...f.timers.values()][0].fn();
  f.respond(f.state);
  await next;
  assert.equal(f.requests.length, 2);
  assert.equal(f.timers.size, 1);
});
