'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const os = require('node:os');

const {
  BUILTIN_REGISTRIES,
  resolveEffectiveRegistry,
  matchBuiltinName,
  maskCredentials,
  applyRegistry,
  atomicWriteFile,
  readRegistryFromFile,
} = require('../src/registry');

function tmpDir() {
  return fs.mkdtempSync(path.join(os.tmpdir(), 'mirr-npm-test-'));
}

test('BUILTIN_REGISTRIES has the four expected entries', () => {
  const names = BUILTIN_REGISTRIES.map((entry) => entry.name).sort();
  assert.deepEqual(names, ['huawei', 'npmjs', 'npmmirror', 'tencent']);
  const npmjs = BUILTIN_REGISTRIES.find((entry) => entry.name === 'npmjs');
  assert.equal(npmjs.url, 'https://registry.npmjs.org');
});

test('resolveEffectiveRegistry: environment variable wins', () => {
  const dir = tmpDir();
  fs.writeFileSync(path.join(dir, '.npmrc'), 'registry=https://from-file.example\n');
  const result = resolveEffectiveRegistry({
    env: { npm_config_registry: 'https://from-env.example' },
    home: dir,
  });
  assert.equal(result.url, 'https://from-env.example');
  assert.equal(result.source, 'environment:npm_config_registry');
});

test('resolveEffectiveRegistry: falls back to ~/.npmrc', () => {
  const dir = tmpDir();
  fs.writeFileSync(path.join(dir, '.npmrc'), 'registry=https://from-file.example\n');
  const result = resolveEffectiveRegistry({ env: {}, home: dir });
  assert.equal(result.url, 'https://from-file.example');
  assert.equal(result.source, 'user:.npmrc');
  assert.equal(result.path, path.join(dir, '.npmrc'));
});

test('resolveEffectiveRegistry: falls back to implicit default', () => {
  const dir = tmpDir();
  const result = resolveEffectiveRegistry({ env: {}, home: dir });
  assert.equal(result.url, 'https://registry.npmjs.org');
  assert.equal(result.source, 'implicit:npmjs');
});

test('readRegistryFromFile: skips comments and scoped overrides', () => {
  const dir = tmpDir();
  const file = path.join(dir, '.npmrc');
  fs.writeFileSync(
    file,
    ['# comment: registry=https://ignored.example', '@corp:registry=https://scoped.example', 'registry=https://real.example'].join('\n') + '\n'
  );
  assert.equal(readRegistryFromFile(file), 'https://real.example');
});

test('matchBuiltinName: matches and rejects', () => {
  assert.equal(matchBuiltinName('https://registry.npmjs.org'), 'npmjs');
  assert.equal(matchBuiltinName('https://registry.npmjs.org/'), 'npmjs');
  assert.equal(matchBuiltinName('https://example.com/custom'), null);
});

test('maskCredentials: strips embedded userinfo', () => {
  const masked = maskCredentials('https://alice:secret@registry.example/path');
  assert.ok(!masked.includes('secret'));
  assert.ok(!masked.includes('alice'));
  assert.equal(maskCredentials('https://registry.example/path'), 'https://registry.example/path');
});

test('applyRegistry: replaces existing line, keeps comments and scoped overrides', () => {
  const original = ['# a comment', '@corp:registry=https://scoped.example', 'registry=https://old.example', 'save-exact=true'].join('\n') + '\n';
  const updated = applyRegistry(original, 'https://new.example');
  const lines = updated.split('\n');
  assert.ok(lines.includes('# a comment'));
  assert.ok(lines.includes('@corp:registry=https://scoped.example'));
  assert.ok(lines.includes('registry=https://new.example'));
  assert.ok(lines.includes('save-exact=true'));
  assert.ok(!updated.includes('https://old.example'));
});

test('applyRegistry: appends when no registry line exists', () => {
  const updated = applyRegistry('save-exact=true\n', 'https://new.example');
  assert.equal(updated, 'save-exact=true\nregistry=https://new.example\n');
});

test('applyRegistry: appends into an empty file', () => {
  const updated = applyRegistry('', 'https://new.example');
  assert.equal(updated, 'registry=https://new.example\n');
});

test('atomicWriteFile: creates parent dirs and writes content', () => {
  const dir = tmpDir();
  const target = path.join(dir, 'nested', '.npmrc');
  atomicWriteFile(target, 'registry=https://new.example\n');
  assert.equal(fs.readFileSync(target, 'utf8'), 'registry=https://new.example\n');
});

test('atomicWriteFile: no leftover temp file after a successful write', () => {
  const dir = tmpDir();
  const target = path.join(dir, '.npmrc');
  fs.writeFileSync(target, 'registry=https://old.example\n');
  atomicWriteFile(target, 'registry=https://new.example\n');
  const leftovers = fs.readdirSync(dir).filter((name) => name !== '.npmrc');
  assert.deepEqual(leftovers, []);
});

test('atomicWriteFile: failed write leaves no temp file and the original untouched', { skip: process.getuid && process.getuid() === 0 ? 'root bypasses permission checks' : false }, () => {
  const dir = tmpDir();
  const target = path.join(dir, '.npmrc');
  fs.writeFileSync(target, 'registry=https://old.example\n');
  fs.chmodSync(dir, 0o500);
  try {
    assert.throws(() => atomicWriteFile(target, 'registry=https://new.example\n'));
  } finally {
    fs.chmodSync(dir, 0o700);
  }
  assert.equal(fs.readFileSync(target, 'utf8'), 'registry=https://old.example\n');
  const leftovers = fs.readdirSync(dir).filter((name) => name !== '.npmrc');
  assert.deepEqual(leftovers, []);
});
