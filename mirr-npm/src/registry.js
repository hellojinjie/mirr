'use strict';

const fs = require('fs');
const os = require('os');
const path = require('path');

// Same URLs as BUILTIN_NPM_INDEXES in src/mirr/catalog.py (Python mirr).
const BUILTIN_REGISTRIES = [
  { name: 'npmjs', url: 'https://registry.npmjs.org' },
  { name: 'npmmirror', url: 'https://registry.npmmirror.com' },
  { name: 'tencent', url: 'https://mirrors.cloud.tencent.com/npm/' },
  { name: 'huawei', url: 'https://repo.huaweicloud.com/repository/npm/' },
];

const COMMENT_PREFIXES = ['#', ';'];
const REGISTRY_RE = /^\s*registry\s*=\s*(.*?)\s*$/;

function isCommentLine(line) {
  const trimmed = line.replace(/^\s+/, '');
  return COMMENT_PREFIXES.some((prefix) => trimmed.startsWith(prefix));
}

function userNpmrcPath({ env = process.env, home = os.homedir() } = {}) {
  const override = env.npm_config_userconfig;
  if (override) return override;
  return path.join(home, '.npmrc');
}

function readRegistryFromFile(filePath) {
  let text;
  try {
    text = fs.readFileSync(filePath, 'utf8');
  } catch {
    return null;
  }
  let value = null;
  for (const rawLine of text.split(/\r\n|\n/)) {
    if (isCommentLine(rawLine)) continue;
    const match = REGISTRY_RE.exec(rawLine);
    if (match) value = match[1];
  }
  return value || null;
}

function resolveEffectiveRegistry({ env = process.env, home = os.homedir() } = {}) {
  const envValue = env.npm_config_registry;
  if (envValue) {
    return { url: envValue, source: 'environment:npm_config_registry', path: null };
  }

  const userPath = userNpmrcPath({ env, home });
  if (fs.existsSync(userPath)) {
    const value = readRegistryFromFile(userPath);
    if (value !== null) {
      return { url: value, source: 'user:.npmrc', path: userPath };
    }
  }

  return { url: 'https://registry.npmjs.org', source: 'implicit:npmjs', path: null };
}

function normalizeUrl(url) {
  let parsed;
  try {
    parsed = new URL(url);
  } catch {
    return url;
  }
  let pathname = parsed.pathname.replace(/\/+$/, '');
  if (!pathname) pathname = '/';
  return `${parsed.protocol}//${parsed.host.toLowerCase()}${pathname}${parsed.search}${parsed.hash}`;
}

function matchBuiltinName(url) {
  const normalized = normalizeUrl(url);
  for (const entry of BUILTIN_REGISTRIES) {
    if (normalizeUrl(entry.url) === normalized) return entry.name;
  }
  return null;
}

function maskCredentials(url) {
  let parsed;
  try {
    parsed = new URL(url);
  } catch {
    return url;
  }
  if (!parsed.username && !parsed.password) return url;
  parsed.password = '';
  parsed.username = '***';
  return parsed.toString();
}

/**
 * Set the top-level `registry`, touching only that one line.
 *
 * Scoped overrides (`@corp:registry=...`) do not match the bare `registry`
 * key and are left untouched, same as every other unrelated line.
 */
function applyRegistry(text, url) {
  const lines = text.length ? text.split(/(?<=\n)/) : [];
  let keyLine = -1;
  for (let index = 0; index < lines.length; index += 1) {
    if (isCommentLine(lines[index])) continue;
    if (REGISTRY_RE.test(lines[index])) keyLine = index;
  }

  const newLine = `registry=${url}\n`;
  if (keyLine !== -1) {
    lines[keyLine] = newLine;
    return lines.join('');
  }

  let textSoFar = lines.join('');
  if (textSoFar && !textSoFar.endsWith('\n')) textSoFar += '\n';
  return textSoFar + newLine;
}

/** Atomically replace `filePath` with `content`, preserving permissions if it exists. */
function atomicWriteFile(filePath, content) {
  const dir = path.dirname(filePath);
  fs.mkdirSync(dir, { recursive: true });

  let existingMode;
  try {
    existingMode = fs.statSync(filePath).mode;
  } catch {
    existingMode = undefined;
  }

  const tmpPath = path.join(dir, `.${path.basename(filePath)}.${process.pid}.${Date.now()}.tmp`);
  let cleanup = true;
  try {
    fs.writeFileSync(tmpPath, content, 'utf8');
    if (existingMode !== undefined) fs.chmodSync(tmpPath, existingMode);
    fs.renameSync(tmpPath, filePath);
    cleanup = false;
  } finally {
    if (cleanup) {
      try {
        fs.unlinkSync(tmpPath);
      } catch {
        // best-effort cleanup only
      }
    }
  }
}

function pingUrl(registryUrl) {
  return registryUrl.replace(/\/+$/, '') + '/-/ping';
}

/** Probe one registry: HEAD first, GET fallback if the server rejects HEAD. */
async function probeRegistry(registryUrl, { timeoutMs = 5000 } = {}) {
  const target = pingUrl(registryUrl);
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  const start = Date.now();
  try {
    let response = await fetch(target, { method: 'HEAD', signal: controller.signal });
    if (response.status === 405 || response.status === 501) {
      response = await fetch(target, { method: 'GET', signal: controller.signal });
    }
    const latencyMs = Date.now() - start;
    if (response.body && typeof response.body.cancel === 'function') {
      await response.body.cancel().catch(() => {});
    }
    if (response.ok) {
      return { ok: true, latencyMs, error: null };
    }
    return { ok: false, latencyMs: null, error: `HTTP ${response.status}` };
  } catch (error) {
    if (error && error.name === 'AbortError') {
      return { ok: false, latencyMs: null, error: 'timeout' };
    }
    return { ok: false, latencyMs: null, error: error && error.message ? error.message : String(error) };
  } finally {
    clearTimeout(timer);
  }
}

module.exports = {
  BUILTIN_REGISTRIES,
  userNpmrcPath,
  readRegistryFromFile,
  resolveEffectiveRegistry,
  normalizeUrl,
  matchBuiltinName,
  maskCredentials,
  applyRegistry,
  atomicWriteFile,
  pingUrl,
  probeRegistry,
};
