PICKER_HTML = r"""<!DOCTYPE html>
<html lang="zh-Hant-TW">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>花曆挑片</title>
<style>
:root{--paper:#F5F7F1;--ink:#1D3A2F;--leaf:#5B7C58;--mist:#DCE3D5;--bloom:#B8336A;--panel:#fff;
  --serif:"Noto Serif TC","Songti TC",serif;
  --sans:"PingFang TC","Heiti TC",system-ui,sans-serif}
@media (prefers-color-scheme:dark){:root{--paper:#121A16;--ink:#E4ECE2;--leaf:#9DBB98;--mist:#2A362F;--bloom:#E76D9F;--panel:#18221D}}
*{box-sizing:border-box}
body{margin:0;background:var(--paper);color:var(--ink);font-family:var(--sans);
  display:grid;grid-template-columns:300px 1fr;height:100vh;overflow:hidden}
aside{border-right:1px solid var(--mist);display:flex;flex-direction:column;min-height:0}
.bar{padding:12px;border-bottom:1px solid var(--mist);display:grid;gap:8px}
input[type=search]{font:inherit;padding:9px 12px;border:1px solid var(--mist);border-radius:9px;
  background:var(--panel);color:var(--ink);width:100%}
.filters{display:flex;gap:6px;flex-wrap:wrap}
.f{font:inherit;font-size:13px;padding:4px 10px;border-radius:999px;border:1px solid var(--mist);
  background:transparent;color:var(--ink);cursor:pointer}
.f[aria-pressed=true]{background:var(--ink);color:var(--paper);border-color:var(--ink)}
#list{overflow-y:auto;flex:1;min-height:0}
#list button{display:flex;width:100%;align-items:center;gap:8px;font:inherit;text-align:left;
  padding:9px 12px;border:0;border-bottom:1px solid var(--mist);background:transparent;
  color:var(--ink);cursor:pointer}
#list button:hover{background:var(--mist)}
#list button[aria-current=true]{background:var(--ink);color:var(--paper)}
#list .nm{font-family:var(--serif);font-weight:700;flex:1;min-width:0;
  overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
#list .ct{font-size:12px;opacity:.6;font-variant-numeric:tabular-nums}
#list .dot{width:7px;height:7px;border-radius:50%;background:var(--bloom);flex:none;visibility:hidden}
#list button.edited .dot{visibility:visible}
main{overflow-y:auto;padding:18px 22px 60px;min-height:0}
h1{font-family:var(--serif);font-size:30px;margin:0 0 2px}
.meta{color:var(--leaf);font-size:14px;margin:0 0 14px}
.acts{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:16px;position:sticky;top:0;
  background:var(--paper);padding:6px 0 10px;z-index:2}
.btn{font:inherit;font-size:14px;padding:7px 14px;border-radius:9px;border:1px solid var(--ink);
  background:transparent;color:var(--ink);cursor:pointer}
.btn.solid{background:var(--bloom);border-color:var(--bloom);color:#fff}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:10px}
.cell{position:relative;border-radius:10px;overflow:hidden;cursor:pointer;background:var(--mist);
  aspect-ratio:1;border:3px solid transparent;padding:0}
.cell img{width:100%;height:100%;object-fit:cover;display:block}
.cell[data-sel]{border-color:var(--bloom)}
.cell .b{position:absolute;top:6px;left:6px;width:26px;height:26px;border-radius:50%;
  background:var(--bloom);color:#fff;font-weight:700;font-size:14px;display:none;
  align-items:center;justify-content:center}
.cell[data-sel] .b{display:flex}
.cell[data-sel="1"] .b::after{content:"大"}
.cell .dt{position:absolute;left:0;right:0;bottom:0;font-size:11px;color:#fff;padding:12px 6px 4px;
  background:linear-gradient(transparent,rgba(0,0,0,.6))}
.hint{color:var(--leaf);font-size:13px;margin:16px 0 0;line-height:1.7}
.done{position:fixed;right:18px;bottom:18px;background:var(--ink);color:var(--paper);
  padding:10px 16px;border-radius:10px;font-size:14px;box-shadow:0 3px 14px rgba(0,0,0,.2)}
@media (max-width:820px){body{grid-template-columns:1fr;grid-template-rows:44vh 1fr}
  aside{border-right:0;border-bottom:1px solid var(--mist)}}
</style>
</head>
<body>
<aside>
  <div class="bar">
    <input type="search" id="q" placeholder="搜尋花名…" autocomplete="off" />
    <div class="filters">
      <button class="f" id="fAll" aria-pressed="true">全部</button>
      <button class="f" id="fEd" aria-pressed="false">已調整</button>
      <button class="f" id="fMany" aria-pressed="false">5 張以上</button>
    </div>
  </div>
  <div id="list"></div>
</aside>
<main>
  <h1 id="nm">—</h1>
  <p class="meta" id="mt"></p>
  <div class="acts">
    <button class="btn" id="auto">回到自動挑選</button>
    <button class="btn" id="clear">全部取消</button>
    <button class="btn solid" id="exp">匯出 photo_picks.json</button>
    <button class="btn" id="prev">← 上一種</button>
    <button class="btn" id="next">下一種 →</button>
  </div>
  <div class="grid" id="g"></div>
  <p class="hint">
    點照片選取，再點一次取消。<b>第一張選的就是大圖</b>，其餘依點選順序排在下面，最多 4 張。<br />
    左邊清單有紅點的是你調整過的。改完按「匯出」，把下載到的 photo_picks.json 給我，或自己放到
    smallflower-web/tools/ 底下再重跑一次程式。<br />
    進度會自動存在這台電腦的瀏覽器裡，關掉再開還在。
  </p>
</main>
<div class="done" id="done"></div>
<script>
const DATA = __DATA__;
const AUTO = DATA.current, SP = DATA.species;
const KEY = 'huali-picks-v1';
let picks = {};
try { picks = JSON.parse(localStorage.getItem(KEY) || '{}'); } catch (e) { picks = {}; }
const names = Object.keys(SP).sort((a, b) => a.localeCompare(b, 'zh-Hant'));
let cur = names[0], mode = 'all', q = '';

const $ = (id) => document.getElementById(id);
const sel = (n) => picks[n] || AUTO[n] || [];
const save = () => { try { localStorage.setItem(KEY, JSON.stringify(picks)); } catch (e) {} };

function shown() {
  return names.filter((n) => {
    if (q && !n.includes(q)) return false;
    if (mode === 'ed' && !picks[n]) return false;
    if (mode === 'many' && SP[n].n < 5) return false;
    return true;
  });
}
function drawList() {
  const f = document.createDocumentFragment();
  for (const n of shown()) {
    const b = document.createElement('button');
    b.innerHTML = '<span class="dot"></span><span class="nm"></span><span class="ct">' + SP[n].n + '</span>';
    b.querySelector('.nm').textContent = n;
    if (picks[n]) b.classList.add('edited');
    if (n === cur) b.setAttribute('aria-current', 'true');
    b.onclick = () => { cur = n; drawList(); drawMain(); };
    f.appendChild(b);
  }
  $('list').replaceChildren(f);
  const a = $('list').querySelector('[aria-current]');
  if (a) a.scrollIntoView({ block: 'nearest' });
  $('done').textContent = '已調整 ' + Object.keys(picks).length + ' / ' + names.length + ' 種';
}
function drawMain() {
  const sp = SP[cur], s = sel(cur);
  $('nm').textContent = cur;
  $('mt').textContent = sp.n + ' 張照片　已選 ' + s.length + ' 張' + (picks[cur] ? '（手動）' : '（自動）');
  const f = document.createDocumentFragment();
  for (const p of sp.ph) {
    const c = document.createElement('button');
    c.className = 'cell';
    const i = s.indexOf(p.k);
    if (i >= 0) c.dataset.sel = i + 1;
    c.innerHTML = '<img loading="lazy" decoding="async" src="thumbs/' + sp.s + '/' + p.k +
      '.jpg" alt="" /><span class="b">' + (i >= 0 && i > 0 ? i + 1 : '') +
      '</span><span class="dt">' + (p.d || '') + '</span>';
    c.onclick = () => toggle(p.k);
    f.appendChild(c);
  }
  $('g').replaceChildren(f);
}
function toggle(k) {
  const s = sel(cur).slice(), i = s.indexOf(k);
  if (i >= 0) s.splice(i, 1);
  else { if (s.length >= 4) return; s.push(k); }
  picks[cur] = s; save(); drawList(); drawMain();
}
$('auto').onclick = () => { delete picks[cur]; save(); drawList(); drawMain(); };
$('clear').onclick = () => { picks[cur] = []; save(); drawList(); drawMain(); };
const step = (d) => {
  const l = shown(), i = l.indexOf(cur);
  if (i < 0) return;
  cur = l[Math.min(l.length - 1, Math.max(0, i + d))];
  drawList(); drawMain();
};
$('next').onclick = () => step(1);
$('prev').onclick = () => step(-1);
$('exp').onclick = () => {
  const out = {};
  for (const n in picks) if (picks[n] && picks[n].length) out[n] = picks[n];
  const blob = new Blob([JSON.stringify(out, null, 1)], { type: 'application/json' });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = 'photo_picks.json';
  a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 3000);
};
$('q').oninput = (e) => { q = e.target.value.trim(); drawList(); };
for (const [id, m] of [['fAll', 'all'], ['fEd', 'ed'], ['fMany', 'many']]) {
  $(id).onclick = () => {
    mode = m;
    for (const x of ['fAll', 'fEd', 'fMany']) $(x).setAttribute('aria-pressed', String(x === id));
    drawList();
  };
}
document.addEventListener('keydown', (e) => {
  if (e.target.tagName === 'INPUT') return;
  if (e.key === 'ArrowDown' || e.key === 'j') { e.preventDefault(); step(1); }
  if (e.key === 'ArrowUp' || e.key === 'k') { e.preventDefault(); step(-1); }
});
drawList(); drawMain();
</script>
</body>
</html>
"""
