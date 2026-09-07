'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const http = require('node:http');

const { probeRegistry } = require('../src/registry');

function listen(server) {
  return new Promise((resolve) => {
    server.listen(0, '127.0.0.1', () => resolve(server.address().port));
  });
}

function close(server) {
  return new Promise((resolve) => server.close(resolve));
}

test('probeRegistry: succeeds on a server that answers HEAD', async () => {
  const server = http.createServer((req, res) => {
    res.writeHead(200);
    res.end();
  });
  const port = await listen(server);
  try {
    const result = await probeRegistry(`http://127.0.0.1:${port}`);
    assert.equal(result.ok, true);
    assert.equal(typeof result.latencyMs, 'number');
  } finally {
    await close(server);
  }
});

test('probeRegistry: falls back to GET when HEAD is rejected', async () => {
  const server = http.createServer((req, res) => {
    if (req.method === 'HEAD') {
      res.writeHead(405);
      res.end();
      return;
    }
    res.writeHead(200);
    res.end('pong');
  });
  const port = await listen(server);
  try {
    const result = await probeRegistry(`http://127.0.0.1:${port}`);
    assert.equal(result.ok, true);
  } finally {
    await close(server);
  }
});

test('probeRegistry: reports failure for a non-2xx response', async () => {
  const server = http.createServer((req, res) => {
    res.writeHead(500);
    res.end();
  });
  const port = await listen(server);
  try {
    const result = await probeRegistry(`http://127.0.0.1:${port}`);
    assert.equal(result.ok, false);
    assert.match(result.error, /500/);
  } finally {
    await close(server);
  }
});

test('probeRegistry: reports timeout when the server never responds', async () => {
  const server = http.createServer(() => {
    // never respond
  });
  const port = await listen(server);
  try {
    const result = await probeRegistry(`http://127.0.0.1:${port}`, { timeoutMs: 100 });
    assert.equal(result.ok, false);
    assert.equal(result.error, 'timeout');
  } finally {
    await close(server);
  }
});
