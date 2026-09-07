'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { spawnSync } = require('node:child_process');

const BIN = path.join(__dirname, '..', 'bin', 'mirr.js');

function runCli(args, { home, env = {} } = {}) {
  const dir = home || fs.mkdtempSync(path.join(os.tmpdir(), 'mirr-npm-cli-'));
  const result = spawnSync(process.execPath, [BIN, ...args], {
    encoding: 'utf8',
    env: {
      PATH: process.env.PATH,
      HOME: dir,
      USERPROFILE: dir,
      ...env,
    },
  });
  return { ...result, home: dir };
}

test('cli: no arguments prints usage and exits 0', () => {
  const { status, stdout } = runCli([]);
  assert.equal(status, 0);
  assert.match(stdout, /Usage: mirr/);
});

test('cli: unknown command fails with a non-zero exit code', () => {
  const { status, stderr } = runCli(['bogus']);
  assert.notEqual(status, 0);
  assert.match(stderr, /unknown command: bogus/);
});

test('cli: ls lists the built-in registries', () => {
  const { status, stdout } = runCli(['ls']);
  assert.equal(status, 0);
  assert.match(stdout, /npmjs/);
  assert.match(stdout, /npmmirror/);
  assert.match(stdout, /tencent/);
  assert.match(stdout, /huawei/);
});

test('cli: current reports the implicit default when nothing is configured', () => {
  const { status, stdout } = runCli(['current']);
  assert.equal(status, 0);
  assert.match(stdout, /npmjs/);
});

test('cli: use switches the registry and ls reflects it', () => {
  const home = fs.mkdtempSync(path.join(os.tmpdir(), 'mirr-npm-cli-'));
  const use = runCli(['use', 'npmmirror'], { home });
  assert.equal(use.status, 0);
  assert.match(use.stdout, /SUCCESS/);

  const npmrc = fs.readFileSync(path.join(home, '.npmrc'), 'utf8');
  assert.match(npmrc, /registry=https:\/\/registry\.npmmirror\.com/);

  const ls = runCli(['ls'], { home });
  assert.match(ls.stdout, /\* npmmirror/);

  const current = runCli(['current'], { home });
  assert.match(current.stdout, /npmmirror/);
});

test('cli: use preserves unrelated .npmrc settings', () => {
  const home = fs.mkdtempSync(path.join(os.tmpdir(), 'mirr-npm-cli-'));
  fs.writeFileSync(
    path.join(home, '.npmrc'),
    ['save-exact=true', '@corp:registry=https://scoped.example', 'registry=https://old.example'].join('\n') + '\n'
  );

  const use = runCli(['use', 'tencent'], { home });
  assert.equal(use.status, 0);

  const npmrc = fs.readFileSync(path.join(home, '.npmrc'), 'utf8');
  assert.match(npmrc, /save-exact=true/);
  assert.match(npmrc, /@corp:registry=https:\/\/scoped\.example/);
  assert.match(npmrc, /registry=https:\/\/mirrors\.cloud\.tencent\.com\/npm\//);
  assert.ok(!npmrc.includes('https://old.example'));
});

test('cli: use with an unknown name fails and does not touch the file', () => {
  const home = fs.mkdtempSync(path.join(os.tmpdir(), 'mirr-npm-cli-'));
  const before = 'registry=https://registry.npmjs.org\n';
  fs.writeFileSync(path.join(home, '.npmrc'), before);

  const { status, stderr } = runCli(['use', 'does-not-exist'], { home });
  assert.notEqual(status, 0);
  assert.match(stderr, /unknown index/);
  assert.equal(fs.readFileSync(path.join(home, '.npmrc'), 'utf8'), before);
});

test('cli: use without a name fails and does not create a file', () => {
  const home = fs.mkdtempSync(path.join(os.tmpdir(), 'mirr-npm-cli-'));
  const { status, stderr } = runCli(['use'], { home });
  assert.notEqual(status, 0);
  assert.match(stderr, /name is required/);
  assert.equal(fs.existsSync(path.join(home, '.npmrc')), false);
});

test('cli: current --show-url and --verbose report URL and source', () => {
  const home = fs.mkdtempSync(path.join(os.tmpdir(), 'mirr-npm-cli-'));
  runCli(['use', 'npmjs'], { home });

  const withUrl = runCli(['current', '--show-url'], { home });
  assert.match(withUrl.stdout, /https:\/\/registry\.npmjs\.org/);

  const verbose = runCli(['current', '--verbose'], { home });
  assert.match(verbose.stdout, /Source: user:\.npmrc/);
  assert.match(verbose.stdout, /Path: /);
});

test('cli: current reports the environment override and its source', () => {
  const { status, stdout } = runCli(['current', '--verbose'], {
    env: { npm_config_registry: 'https://from-env.example' },
  });
  assert.equal(status, 0);
  assert.match(stdout, /from-env\.example/);
  assert.match(stdout, /Source: environment:npm_config_registry/);
});
