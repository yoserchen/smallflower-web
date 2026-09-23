import { CALENDARS } from './config.mjs';

const files = import.meta.glob('./data/*.json', { eager: true });
const DATA = {};
for (const p in files) DATA[p.split('/').pop().replace('.json', '')] = files[p].default;

const pfiles = import.meta.glob('./photos/*.json', { eager: true });
const PHOTOS = {};
for (const p in pfiles) PHOTOS[p.split('/').pop().replace('.json', '')] = pfiles[p].default;

export const photosOf = (slug, s) => (PHOTOS[slug] || {})[s.n] || null;
export const coverOf = (slug, s) => {
  const p = photosOf(slug, s);
  return p && p.ph.length ? `/p/${p.s}/${p.ph[0].i}t.jpg` : null;
};

export const calFor = (slug) => CALENDARS.find((c) => c.slug === slug);
export const LIVE_CALENDARS = CALENDARS.filter((c) => (DATA[c.slug] || []).length > 0);
export const speciesOf = (slug) => DATA[slug] || [];
export const liveOf = (slug) => speciesOf(slug).filter((s) => s.st === '現存');

export const has = (s, m) => ((s.m >> (m - 1)) & 1) === 1;
export const monthsOf = (s) => Array.from({ length: 12 }, (_, i) => i + 1).filter((m) => has(s, m));
export const yearsOf = (s) => [0, 1, 2, 3].filter((k) => (s.y >> k) & 1).map((k) => 2023 + k);
export const monthCountOf = (slug) =>
  Array.from({ length: 12 }, (_, i) => liveOf(slug).filter((s) => has(s, i + 1)).length);

const noKey = (n) => { if (!n) return [9, 9999]; const [a, b] = n.split('-').map(Number); return [a, b]; };
export const byNo = (a, b) => {
  const x = noKey(a.no[0]), y = noKey(b.no[0]);
  return x[0] - y[0] || x[1] - y[1] || a.n.localeCompare(b.n, 'zh-Hant');
};
export const url = (slug, s) => `/${slug}/flower/${encodeURIComponent(s.id)}/`;
