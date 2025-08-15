// config.js
const fs = require('fs');
const JSON5 = require('json5');

const read5 = (p) => JSON5.parse(fs.readFileSync(p, 'utf8'));
const merge = (a, b) => {
  if (Array.isArray(a) && Array.isArray(b)) return [...a, ...b];
  if (a && typeof a === 'object' && b && typeof b === 'object') {
    const out = { ...a };
    for (const k of Object.keys(b)) out[k] = k in out ? merge(out[k], b[k]) : b[k];
    return out;
  }
  return b ?? a;
};

// Base (drop the local> lines here)
const base = read5('.renovaterc.json5');

// Merge in your local preset fragments
const parts = [
  '.renovate/autoMerge.json5',
  '.renovate/customManagers.json5',
  '.renovate/grafanaDashboards.json5',
  '.renovate/groups.json5',
  '.renovate/labels.json5',
  '.renovate/semanticCommits.json5',
  '.renovate/talosFactory.json5',
].map(read5);

module.exports = parts.reduce((acc, cur) => merge(acc, cur), base);
