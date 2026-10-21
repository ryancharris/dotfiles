const {test} = require('node:test');
const assert = require('node:assert/strict');
const http = require('node:http');
const {createHash} = require('node:crypto');
const {dispatchRefresh, localOrigin, sendCommand, requestTicket} = require('../scripts/local_t3_refresh.js');

const request = {id: '12345678-1234-4123-8123-123456789abc', action: 'refresh', date: '2026-10-21', timezone: 'America/Toronto'};
const config = {cli_path: '/trusted/t3', runtime_path: '/trusted/userdata/server-runtime.json', thread_id: 'existing-bound-thread', base_dir: '/trusted'};
const input = () => ({config: {...config}, request: {...request}, root: '/configured/report-root'});

function dependencies(overrides = {}) {
  const seen = [];
  return {seen, readFile: async file => {seen.push(['runtime', file]); return JSON.stringify({origin: 'http://127.0.0.1:3773'});},
    realpath: async root => {seen.push(['root', root]); return '/resolved/report-root';},
    issueToken: async (cfg, signal) => {seen.push(['token', cfg.cli_path]); assert.equal(signal.aborted, false); return 'synthetic-bearer';},
    requestTicket: async (origin, token) => {seen.push(['ticket', origin]); assert.equal(token, 'synthetic-bearer'); return 'synthetic-ticket';},
    sendCommand: async (url, command) => {seen.push(['dispatch', url, command]); return {ok: true};}, ...overrides};
}

test('dispatch uses current loopback runtime and only fixed request metadata in an existing thread', async () => {
  const data = input();
  data.request.prompt = 'UNTRUSTED_BROWSER_INSTRUCTIONS';
  data.request.root = '/untrusted-browser-root';
  const deps = dependencies();
  assert.deepEqual(await dispatchRefresh(data, deps), {ok: true});
  assert.deepEqual(deps.seen.map(row => row[0]), ['runtime', 'root', 'token', 'ticket', 'dispatch']);
  const [, target, command] = deps.seen.at(-1);
  const url = new URL(target);
  assert.equal(url.origin, 'ws://127.0.0.1:3773');
  assert.equal(url.pathname, '/ws');
  assert.equal(url.searchParams.get('orchestrationProtocol'), '2');
  assert.equal(url.searchParams.get('wsTicket'), 'synthetic-ticket');
  assert.equal(command.type, 'message.dispatch');
  assert.equal(command.threadId, config.thread_id);
  assert.deepEqual(command.dispatchMode, {type: 'queue_after_active'});
  assert.deepEqual(command.attachments, []);
  assert.equal(command.commandId, 'morning-coffee:' + request.id);
  assert.equal(command.messageId, command.commandId);
  assert.match(command.text, new RegExp(request.id));
  assert.match(command.text, /\/resolved\/report-root/);
  assert.doesNotMatch(command.text, /UNTRUSTED_BROWSER_INSTRUCTIONS|untrusted-browser-root|synthetic-bearer|synthetic-ticket/);
  const retry = dependencies();
  await dispatchRefresh(data, retry);
  assert.deepEqual(retry.seen.at(-1)[2], command, 'a retry reuses durable command/message identity');
});

test('runtime is reread on each dispatch rather than retaining a stale port', async () => {
  let port = 3773;
  const deps = dependencies({readFile: async () => JSON.stringify({origin: 'http://127.0.0.1:' + port})});
  await dispatchRefresh(input(), deps);
  port = 3999;
  await dispatchRefresh(input(), deps);
  assert.deepEqual(deps.seen.filter(row => row[0] === 'ticket').map(row => row[1]), ['http://127.0.0.1:3773', 'http://127.0.0.1:3999']);
});

test('remote, ambiguous and malformed runtime targets fail before token issuance', async () => {
  for (const origin of ['http://example.com:3773', 'http://localhost:3773', 'http://127.0.0.1:3773/',
    'http://127.0.0.1:3773/mcp', 'http://127.0.0.1:3773?secret=leak', 'http://user:pass@127.0.0.1:3773',
    'https://127.0.0.1:3773', 'http://127.0.0.1:65536', 'http://127.0.0.1:03773', 'http://127.1:3773']) {
    assert.throws(() => localOrigin({origin}));
    const deps = dependencies({readFile: async () => JSON.stringify({origin})});
    await assert.rejects(dispatchRefresh(input(), deps), /local source refresh connection is unavailable/);
    assert.equal(deps.seen.length, 0, origin);
  }
});

test('invalid request metadata cannot reach the local credential CLI', async () => {
  for (const patch of [{id: 'arbitrary-message'}, {action: 'delete'}, {date: '2026-02-30'}, {timezone: 'Invalid/Timezone'}]) {
    const data = input(); Object.assign(data.request, patch);
    const deps = dependencies();
    await assert.rejects(dispatchRefresh(data, deps));
    assert.deepEqual(deps.seen, []);
  }
});

test('deadline aborts stalled transport and suppresses backend error details', async () => {
  let signal;
  await assert.rejects(dispatchRefresh(input(), dependencies({timeoutMs: 20,
    requestTicket: async (_, __, value) => {signal = value; return new Promise(() => {});}})), /local source refresh connection is unavailable/);
  assert.equal(signal.aborted, true);
  await assert.rejects(dispatchRefresh(input(), dependencies({issueToken: async () => {throw Error('private-token backend response');}})), error => {
    assert.doesNotMatch(error.message, /private-token/);
    return true;
  });
});

class FakeSocket extends EventTarget {
  static instances = [];
  constructor(url) {super(); this.url = url; this.sent = []; this.closed = false; FakeSocket.instances.push(this);}
  send(message) {this.sent.push(JSON.parse(message));}
  close() {this.closed = true;}
  emit(type, data) {this.dispatchEvent(type === 'message' ? new MessageEvent(type, {data: JSON.stringify(data)}) : new Event(type));}
}

test('Effect RPC requires the exact successful acknowledgement and closes the socket', async () => {
  const controller = new AbortController();
  const command = {type: 'message.dispatch'};
  const result = sendCommand('ws://127.0.0.1:3773/ws', command, controller.signal, FakeSocket);
  const socket = FakeSocket.instances.at(-1);
  socket.emit('open');
  assert.deepEqual(socket.sent, [{_tag: 'Request', id: '1', tag: 'orchestration.dispatchCommand', payload: command, headers: []}]);
  socket.emit('message', {_tag: 'Ping'});
  assert.deepEqual(socket.sent.at(-1), {_tag: 'Pong'});
  socket.emit('message', {_tag: 'Exit', requestId: 'unrelated', exit: {_tag: 'Success', value: {sequence: 1}}});
  assert.equal(socket.closed, false);
  socket.emit('message', [{_tag: 'Exit', requestId: '1', exit: {_tag: 'Success', value: {sequence: 42}}}]);
  assert.deepEqual(await result, {ok: true});
  assert.equal(socket.closed, true);
});

test('RPC failure, malformed sequence, defect and abort are never acknowledgements', async () => {
  for (const response of [
    {_tag: 'Exit', requestId: '1', exit: {_tag: 'Failure', cause: 'private backend text'}},
    {_tag: 'Exit', requestId: '1', exit: {_tag: 'Success', value: {sequence: '1'}}},
    {_tag: 'Exit', requestId: '1', exit: {_tag: 'Success', value: {sequence: -1}}},
    {_tag: 'Exit', requestId: '1', exit: {_tag: 'Success', value: {sequence: 1.5}}},
    {_tag: 'Defect', defect: 'private backend text'}, null,
  ]) {
    const result = sendCommand('ws://127.0.0.1:3773/ws', {}, new AbortController().signal, FakeSocket);
    const socket = FakeSocket.instances.at(-1);
    socket.emit('message', response);
    await assert.rejects(result, error => error.message === 'The local source refresh connection is unavailable.');
    assert.equal(socket.closed, true);
  }
  const controller = new AbortController();
  const result = sendCommand('ws://127.0.0.1:3773/ws', {}, controller.signal, FakeSocket);
  const socket = FakeSocket.instances.at(-1);
  controller.abort();
  await assert.rejects(result);
  assert.equal(socket.closed, true);
});

test('ticket exchange authenticates only to loopback and refuses redirects and invalid responses', async t => {
  let mode = 'success';
  const received = [];
  const server = http.createServer((req, res) => {
    received.push({url: req.url, method: req.method, authorization: req.headers.authorization});
    if (mode === 'redirect') {res.writeHead(302, {Location: 'http://example.com/steal'}); res.end(); return;}
    res.writeHead(200, {'Content-Type': 'application/json'});
    res.end(JSON.stringify(mode === 'success' ? {ticket: 'synthetic-ticket', expiresAt: '2099-01-01T00:00:00Z'} : {ticket: 'expired-ticket', expiresAt: '2000-01-01T00:00:00Z'}));
  });
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  t.after(() => new Promise(resolve => server.close(resolve)));
  const origin = 'http://127.0.0.1:' + server.address().port;
  assert.equal(await requestTicket(origin, 'synthetic-bearer', new AbortController().signal), 'synthetic-ticket');
  mode = 'redirect';
  await assert.rejects(requestTicket(origin, 'synthetic-bearer', new AbortController().signal));
  mode = 'expired';
  await assert.rejects(requestTicket(origin, 'synthetic-bearer', new AbortController().signal));
  assert.equal(received.length, 3);
  assert.ok(received.every(row => row.url === '/api/auth/websocket-ticket' && row.method === 'POST' && row.authorization === 'Bearer synthetic-bearer'));
});

test('native WebSocket sends the actual Effect frame and rejects upgrade redirects', async t => {
  const received = [];
  let redirect = false, redirectedRequests = 0;
  const destination = http.createServer((_, res) => {redirectedRequests++; res.end();});
  destination.on('upgrade', (_, socket) => {redirectedRequests++; socket.destroy();});
  await new Promise(resolve => destination.listen(0, '127.0.0.1', resolve));
  t.after(() => new Promise(resolve => destination.close(resolve)));
  const connections = new Set();
  const server = http.createServer();
  server.on('connection', socket => {connections.add(socket); socket.on('close', () => connections.delete(socket));});
  server.on('upgrade', (req, socket) => {
    if (redirect) {
      socket.end('HTTP/1.1 302 Found\r\nLocation: ws://127.0.0.1:' + destination.address().port + '/steal\r\nContent-Length: 0\r\n\r\n');
      return;
    }
    const accept = createHash('sha1').update(req.headers['sec-websocket-key'] + '258EAFA5-E914-47DA-95CA-C5AB0DC85B11').digest('base64');
    socket.write('HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Accept: ' + accept + '\r\n\r\n');
    let buffered = Buffer.alloc(0), handled = false;
    socket.on('data', chunk => {
      if (handled) return;
      buffered = Buffer.concat([buffered, chunk]);
      if (buffered.length < 2) return;
      let length = buffered[1] & 127, offset = 2;
      if (length === 126) {if (buffered.length < 4) return; length = buffered.readUInt16BE(2); offset = 4;}
      assert.ok(length < 65536, 'fixture frame stays bounded');
      if (buffered.length < offset + 4 + length) return;
      const mask = buffered.subarray(offset, offset + 4), payload = buffered.subarray(offset + 4, offset + 4 + length);
      for (let i = 0; i < payload.length; i++) payload[i] ^= mask[i % 4];
      received.push({url: req.url, frame: JSON.parse(payload.toString())});
      handled = true;
      const response = Buffer.from(JSON.stringify({_tag: 'Exit', requestId: '1', exit: {_tag: 'Success', value: {sequence: 7}}}));
      socket.write(Buffer.concat([Buffer.from([0x81, response.length]), response]));
    });
  });
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  t.after(() => {for (const socket of connections) socket.destroy(); return new Promise(resolve => server.close(resolve));});
  const url = 'ws://127.0.0.1:' + server.address().port + '/ws?orchestrationProtocol=2&wsTicket=synthetic-ticket';
  assert.deepEqual(await sendCommand(url, {type: 'message.dispatch', text: 'synthetic collection'}, AbortSignal.timeout(1000)), {ok: true});
  assert.equal(received.length, 1);
  assert.equal(received[0].frame.tag, 'orchestration.dispatchCommand');
  assert.equal(received[0].frame.payload.text, 'synthetic collection');
  assert.equal(received[0].url, '/ws?orchestrationProtocol=2&wsTicket=synthetic-ticket');
  redirect = true;
  await assert.rejects(sendCommand(url, {}, AbortSignal.timeout(1000)));
  assert.equal(redirectedRequests, 0, 'the native WebSocket does not forward a ticket to redirect destinations');
});
