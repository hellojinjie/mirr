#!/usr/bin/env node
'use strict';

const fs = require('fs');

const {
  BUILTIN_REGISTRIES,
  resolveEffectiveRegistry,
  matchBuiltinName,
  maskCredentials,
  applyRegistry,
  atomicWriteFile,
  userNpmrcPath,
  probeRegistry,
} = require('../src/registry');

function log(message) {
  process.stdout.write(`[npm] ${message}\n`);
}

function fail(message) {
  process.stderr.write(`[npm] ${message}\n`);
  process.exitCode = 1;
}

function findEntry(name) {
  return BUILTIN_REGISTRIES.find((entry) => entry.name === name) || null;
}

const colorEnabled = process.stdout.isTTY && !process.env.NO_COLOR;

function colorize(text, code) {
  return colorEnabled ? `\x1b[${code}m${text}\x1b[0m` : text;
}

const BOLD_GREEN = '1;32';
const BRIGHT_GREEN_BG = '102';

function cmdLs() {
  const effective = resolveEffectiveRegistry();
  const currentName = matchBuiltinName(effective.url);
  const width = Math.max(...BUILTIN_REGISTRIES.map((entry) => entry.name.length));
  for (const entry of BUILTIN_REGISTRIES) {
    const marker = entry.name === currentName ? '*' : ' ';
    log(`${marker} ${entry.name.padEnd(width)} --- ${entry.url}`);
  }
  if (currentName === null) {
    log(`Current: ${maskCredentials(effective.url)}`);
  }
}

function cmdCurrent(args) {
  const showUrl = args.includes('-u') || args.includes('--show-url');
  const verbose = args.includes('-v') || args.includes('--verbose');
  const effective = resolveEffectiveRegistry();
  const name = matchBuiltinName(effective.url);
  const safeUrl = maskCredentials(effective.url);

  if (name === null) {
    log(`Your current registry (${safeUrl}) is not one of the built-in mirr-npm registries.`);
  } else {
    log(`You are using ${showUrl ? safeUrl : name} registry.`);
  }

  if (verbose) {
    if (!showUrl && name !== null) {
      log(`URL: ${safeUrl}`);
    }
    log(`Source: ${effective.source}`);
    if (effective.path) {
      log(`Path: ${effective.path}`);
    }
  }
}

function cmdUse(args) {
  const name = args[0];
  if (!name) {
    fail('index name is required');
    return;
  }

  const entry = findEntry(name);
  if (!entry) {
    fail(`unknown index: ${name}`);
    return;
  }

  const targetPath = userNpmrcPath();
  let text = '';
  try {
    text = fs.existsSync(targetPath) ? fs.readFileSync(targetPath, 'utf8') : '';
  } catch (error) {
    fail(`cannot read npm configuration ${targetPath}: ${error.message}`);
    return;
  }

  const updated = applyRegistry(text, entry.url);
  try {
    atomicWriteFile(targetPath, updated);
  } catch (error) {
    fail(`cannot replace configuration ${targetPath}: ${error.message}`);
    return;
  }

  log(`SUCCESS The index has been changed to '${name}'.`);
}

async function cmdTest(args) {
  const name = args[0];
  let entries = BUILTIN_REGISTRIES;
  if (name) {
    const entry = findEntry(name);
    if (!entry) {
      fail(`unknown index: ${name}`);
      return;
    }
    entries = [entry];
  }

  const effective = resolveEffectiveRegistry();
  const currentName = matchBuiltinName(effective.url);

  const results = await Promise.all(
    entries.map(async (entry) => ({ entry, result: await probeRegistry(entry.url) }))
  );

  const width = Math.max(...results.map((row) => row.entry.name.length)) + 3;
  const latencies = results
    .filter((row) => row.result.ok)
    .map((row) => row.result.latencyMs);
  const fastest = latencies.length ? Math.min(...latencies) : null;

  let failed = false;
  for (const { entry, result } of results) {
    const prefix = entry.name === currentName ? colorize('* ', BOLD_GREEN) : '  ';
    const dashCount = Math.max(1, width - entry.name.length + 1);
    const separator = '-'.repeat(dashCount);
    let suffix;
    if (result.ok) {
      suffix = `${result.latencyMs} ms`;
      if (fastest !== null && result.latencyMs === fastest) {
        suffix = colorize(suffix, BRIGHT_GREEN_BG);
      }
    } else {
      failed = true;
      suffix = result.error || 'Fetch error';
    }
    log(`${prefix}${entry.name} ${separator} ${suffix}`);
  }

  if (failed) process.exitCode = 1;
}

async function main() {
  const [, , verb, ...rest] = process.argv;

  switch (verb) {
    case 'ls':
      cmdLs();
      break;
    case 'current':
      cmdCurrent(rest);
      break;
    case 'use':
      cmdUse(rest);
      break;
    case 'test':
      await cmdTest(rest);
      break;
    case undefined:
      process.stdout.write('Usage: mirr <ls|current|use|test> [args]\n');
      break;
    default:
      fail(`unknown command: ${verb}`);
      process.stderr.write('Usage: mirr <ls|current|use|test> [args]\n');
  }
}

main();
