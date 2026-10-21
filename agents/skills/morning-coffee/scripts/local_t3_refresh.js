#!/usr/bin/env node
'use strict';

// A loopback-only T3 bearer client. Tokens and WebSocket tickets stay in memory.
const fs = require('node:fs/promises');
const http = require('node:http');
const path = require('node:path');
const {execFile} = require('node:child_process');

const FAILURE = 'The local source refresh connection is unavailable.';
const DEADLINE_MS = 12000;
const validText = value => typeof value === 'string' && value.length > 0 && value.length <= 4096 && !/[\x00-\x1f\x7f]/.test(value);
const absolutePath = value => validText(value) && path.isAbsolute(value);

function validateInput(input) {
  const config = input?.config, request = input?.request;
  if (!config || !absolutePath(config.cli_path) || !absolutePath(config.runtime_path) ||
      !validText(config.thread_id) || config.thread_id.length > 256 ||
      (config.base_dir !== undefined && !absolutePath(config.base_dir)) ||
      (input.root !== undefined && !absolutePath(input.root)) ||
      !request || typeof request.id !== 'string' || !/^[a-f0-9]{8}-(?:[a-f0-9]{4}-){3}[a-f0-9]{12}$/i.test(request.id) ||
      !['refresh', 'start_today'].includes(request.action) ||
      typeof request.date !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(request.date) ||
      !validText(request.timezone)) throw Error(FAILURE);
  const parsed = new Date(request.date + 'T00:00:00Z');
  if (!Number.isFinite(parsed.getTime()) || parsed.toISOString().slice(0, 10) !== request.date) throw Error(FAILURE);
  new Intl.DateTimeFormat('en', {timeZone: request.timezone});
  return {config, request};
}

function localOrigin(runtime) {
  if (typeof runtime?.origin !== 'string' || !/^http:\/\/127\.0\.0\.1:[1-9]\d{0,4}$/.test(runtime.origin)) throw Error(FAILURE);
  const url = new URL(runtime.origin);
  if (!url.port || Number(url.port) > 65535 || url.origin !== runtime.origin) throw Error(FAILURE);
  return url.origin;
}

function issueToken(config, signal) {
  const args = ['auth', 'session', 'issue', '--scope', 'orchestration:operate', '--ttl', '5m', '--token-only'];
  if (config.base_dir) args.push('--base-dir', config.base_dir);
  return new Promise((resolve, reject) => {
    execFile(config.cli_path, args, {signal, timeout: DEADLINE_MS, maxBuffer: 16384}, (error, stdout) => {
      if (error) return reject(Error(FAILURE));
      const token = stdout.trim();
      if (!token || /\s/.test(token) || token.length > 8192) return reject(Error(FAILURE));
      resolve(token);
    });
  });
}

function requestTicket(origin, token, signal) {
  return new Promise((resolve, reject) => {
    const request = http.request(new URL('/api/auth/websocket-ticket', origin), {
      method: 'POST', signal,
      headers: {Authorization: 'Bearer ' + token, Accept: 'application/json', 'Content-Length': '0'},
    }, response => {
      // Native HTTP never follows redirects; no credential can leave loopback.
      if (response.statusCode !== 200) {response.resume(); reject(Error(FAILURE)); return;}
      let body = '';
      response.setEncoding('utf8');
      response.on('data', chunk => {
        body += chunk;
        if (body.length > 16384) {response.destroy(); reject(Error(FAILURE));}
      });
      response.on('error', () => reject(Error(FAILURE)));
      response.on('end', () => {
        try {
          const result = JSON.parse(body);
          if (!validText(result.ticket) || !Number.isFinite(Date.parse(result.expiresAt)) || Date.parse(result.expiresAt) <= Date.now()) throw Error(FAILURE);
          resolve(result.ticket);
        } catch (_) {reject(Error(FAILURE));}
      });
    });
    request.on('error', () => reject(Error(FAILURE)));
    request.end();
  });
}

function collectionCommand(config, request, root) {
  const skill = path.resolve(__dirname, '..', 'SKILL.md');
  const prompt = [
    'A user explicitly requested a Morning Coffee source refresh from the local dashboard.',
    'Follow the installed Morning Coffee skill at ' + JSON.stringify(skill) + ' and its workspace/source collection workflow.',
    root ? 'Use the report root resolved by the trusted local launcher: ' + JSON.stringify(root) + '.' : 'Resolve the configured report root locally using that workflow.',
    'Inspect the durable workspace first. Proceed only if its current pending/running request exactly matches this metadata: ' + JSON.stringify({refresh_id: request.id, action: request.action, date: request.date, timezone: request.timezone}) + '.',
    'Collect all six sources with honest coverage, preserve local choices, publish the refresh and complete that exact refresh_id. If it is stale, do nothing. If collection fails, fail that exact request safely.',
    'This is a collection request in this existing thread. Do not create another thread or change schedules, connection settings, or provider access.',
  ].join('\n');
  const id = 'morning-coffee:' + request.id;
  return {type: 'message.dispatch', commandId: id, threadId: config.thread_id, messageId: id,
    text: prompt, attachments: [], dispatchMode: {type: 'queue_after_active'}, createdBy: 'user', creationSource: 'server'};
}

function sendCommand(url, command, signal, Socket = WebSocket) {
  return new Promise((resolve, reject) => {
    // Node's native WebSocket handshake rejects redirects.
    const socket = new Socket(url);
    let settled = false;
    const finish = ok => {
      if (settled) return;
      settled = true;
      signal.removeEventListener('abort', abort);
      try {socket.close();} catch (_) {}
      if (ok) resolve({ok: true}); else reject(Error(FAILURE));
    };
    const abort = () => finish(false);
    signal.addEventListener('abort', abort, {once: true});
    if (signal.aborted) {finish(false); return;}
    socket.addEventListener('open', () => {
      if (!settled) socket.send(JSON.stringify({_tag: 'Request', id: '1', tag: 'orchestration.dispatchCommand', payload: command, headers: []}));
    });
    socket.addEventListener('message', event => {
      try {
        const messages = JSON.parse(event.data);
        for (const message of Array.isArray(messages) ? messages : [messages]) {
          if (message._tag === 'Ping') {socket.send(JSON.stringify({_tag: 'Pong'})); continue;}
          if (message._tag === 'Defect') {finish(false); return;}
          if (message._tag !== 'Exit' || message.requestId !== '1') continue;
          const sequence = message.exit?.value?.sequence;
          finish(message.exit?._tag === 'Success' && Number.isSafeInteger(sequence) && sequence >= 0);
          return;
        }
      } catch (_) {finish(false);}
    });
    socket.addEventListener('error', () => finish(false));
    socket.addEventListener('close', () => finish(false));
  });
}

async function dispatchRefresh(input, dependencies = {}) {
  const {config, request} = validateInput(input);
  const controller = new AbortController();
  let timer;
  const deadline = new Promise((_, reject) => {
    timer = setTimeout(() => {controller.abort(); reject(Error(FAILURE));}, dependencies.timeoutMs ?? DEADLINE_MS);
  });
  try {
    return await Promise.race([deadline, (async () => {
      const runtime = JSON.parse(await (dependencies.readFile ?? fs.readFile)(config.runtime_path, 'utf8'));
      const origin = localOrigin(runtime);
      const root = input.root === undefined ? undefined : await (dependencies.realpath ?? fs.realpath)(input.root);
      const token = await (dependencies.issueToken ?? issueToken)(config, controller.signal);
      if (controller.signal.aborted) throw Error(FAILURE);
      const ticket = await (dependencies.requestTicket ?? requestTicket)(origin, token, controller.signal);
      if (controller.signal.aborted) throw Error(FAILURE);
      const url = new URL('/ws', origin);
      url.protocol = 'ws:';
      url.searchParams.set('orchestrationProtocol', '2');
      url.searchParams.set('wsTicket', ticket);
      return await (dependencies.sendCommand ?? sendCommand)(url.toString(), collectionCommand(config, request, root), controller.signal);
    })()]);
  } catch (_) {throw Error(FAILURE);}
  finally {clearTimeout(timer); controller.abort();}
}

module.exports = {dispatchRefresh, validateInput, localOrigin, collectionCommand, sendCommand, requestTicket, issueToken};

if (require.main === module) {
  let input = '';
  const inputDeadline = setTimeout(() => {process.stdout.write(JSON.stringify({ok: false, error: FAILURE}) + '\n', () => process.exit(1));}, DEADLINE_MS);
  process.stdin.setEncoding('utf8');
  process.stdin.on('data', chunk => {
    input += chunk;
    if (input.length > 32768) {process.stdout.write(JSON.stringify({ok: false, error: FAILURE}) + '\n', () => process.exit(1));}
  });
  process.stdin.on('end', async () => {
    try {
      const result = await dispatchRefresh(JSON.parse(input));
      clearTimeout(inputDeadline);
      process.stdout.write(JSON.stringify(result) + '\n', () => process.exit(0));
    } catch (_) {
      clearTimeout(inputDeadline);
      process.stdout.write(JSON.stringify({ok: false, error: FAILURE}) + '\n', () => process.exit(1));
    }
  });
}
