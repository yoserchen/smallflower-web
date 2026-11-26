// Q故事：93 篇故事，從 WordPress 搬過來的（tools/故事轉檔.py）。
// 原本掛在 qstory.timestory.club，主機退租後全部住進這裡。
//
// 每篇文末小花老師都寫了「＃半邊蓮」這種標記，記下照片裡的花。
// f 是對得上台北植物園主檔的花（可以互連），o 是園外的花、昆蟲或別名（只顯示，不連結）。
import DATA from './stories.json';

export const STORIES = DATA;

// 分類：一篇常常掛好幾個，所以用篩選而不是分區，才不用決定「它到底屬於哪一類」
export const CATS = (() => {
  const c = {};
  DATA.forEach((s) => s.c.forEach((x) => { c[x] = (c[x] || 0) + 1; }));
  return Object.entries(c).sort((a, b) => b[1] - a[1]);
})();

const BY_FLOWER = (() => {
  const m = {};
  DATA.forEach((s) => s.f.forEach((n) => { (m[n] = m[n] || []).push(s); }));
  return m;
})();

export const storiesForFlower = (n) => BY_FLOWER[n] || [];
export const storyUrl = (s) => `/story/${s.id}/`;
export const cover = (s, thumb) => (s.cv ? `/s/${thumb ? 't/' : ''}${s.cv}` : null);
