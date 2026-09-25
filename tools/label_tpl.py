LABEL_HTML = r"""<!DOCTYPE html>
<html lang="zh-Hant-TW">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>花曆標註</title>
<style>
:root{--paper:#F5F7F1;--ink:#1D3A2F;--leaf:#5B7C58;--mist:#DCE3D5;--bloom:#B8336A;--panel:#fff;
  --serif:"Noto Serif TC","Songti TC",serif;--sans:"PingFang TC","Heiti TC",system-ui,sans-serif}
@media (prefers-color-scheme:dark){:root{--paper:#121A16;--ink:#E4ECE2;--leaf:#9DBB98;--mist:#2A362F;--bloom:#E76D9F;--panel:#18221D}}
*{box-sizing:border-box}
body{margin:0;background:var(--paper);color:var(--ink);font-family:var(--sans)}
header{position:sticky;top:0;z-index:5;background:var(--paper);border-bottom:1px solid var(--mist);
  padding:12px 20px;display:flex;gap:12px;align-items:center;flex-wrap:wrap}
h1{font-family:var(--serif);font-size:20px;margin:0 16px 0 0}
.btn{font:inherit;font-size:14px;padding:7px 14px;border-radius:9px;border:1px solid var(--ink);
  background:transparent;color:var(--ink);cursor:pointer}
.btn.solid{background:var(--bloom);border-color:var(--bloom);color:#fff}
.btn:disabled{opacity:.4;cursor:not-allowed}
.stat{margin-left:auto;font-size:14px;color:var(--leaf);font-variant-numeric:tabular-nums}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(230px,1fr));gap:14px;padding:18px 20px 80px}
.card{background:var(--panel);border:1px solid var(--mist);border-radius:14px;overflow:hidden;
  display:flex;flex-direction:column}
.card.done{border-color:var(--leaf)}
.card.neu{border-color:var(--bloom)}
.card img{width:100%;aspect-ratio:1;object-fit:cover;display:block;background:var(--mist);cursor:zoom-in}
.body{padding:9px 10px 11px;display:grid;gap:6px}
.dt{font-size:12px;color:var(--leaf);display:flex;justify-content:space-between;align-items:center}
.badge{font-size:11px;background:var(--bloom);color:#fff;border-radius:999px;padding:1px 8px}
input,select{font:inherit;font-size:14px;width:100%;padding:7px 9px;border:1px solid var(--mist);
  border-radius:8px;background:var(--paper);color:var(--ink)}
input:focus,select:focus{border-color:var(--bloom);outline:none}
select{display:none}
.card.neu select{display:block}
.hint{padding:0 20px 8px;color:var(--leaf);font-size:13px;line-height:1.7}
#lb{position:fixed;inset:0;background:rgba(10,16,13,.94);display:none;z-index:20;
  align-items:center;justify-content:center;cursor:zoom-out}
#lb.on{display:flex}
#lb img{max-width:94vw;max-height:94vh;object-fit:contain;border-radius:8px}
</style>
</head>
<body>
<header>
  <h1>花曆標註</h1>
  <button class="btn" id="same">和上一張同名（S）</button>
  <button class="btn" id="skipAll">把空白的標成不收錄</button>
  <button class="btn solid" id="exp">匯出 新增記錄.json</button>
  <span class="stat" id="stat"></span>
</header>
<p class="hint">
  在每張照片下面打花名，打兩三個字會自動列出候選。<b>打完按 Enter 跳下一張</b>；按 S 沿用上一張的花名（連拍很好用）。<br />
  主檔裡沒有的花名會變成<b style="color:var(--bloom)">粉紅色框</b>並要求你選區域 —— 那表示這是新增的花。確定名字沒打錯再送出。<br />
  標好的會自動存在瀏覽器裡，關掉再開還在。全部標完按「匯出」，把檔案放到 <code>花曆更新/</code> 底下。
</p>
<div class="grid" id="g"></div>
<datalist id="names"></datalist>
<div id="lb"><img id="lbimg" alt="" /></div>
<script>
const DATA = __DATA__;
const KEY = 'huali-label-' + DATA.batch;
let mark = {};
try { mark = JSON.parse(localStorage.getItem(KEY) || '{}'); } catch (e) { mark = {}; }
const save = () => { try { localStorage.setItem(KEY, JSON.stringify(mark)); } catch (e) {} };
const known = DATA.species;            // 花名 -> 區域
const names = Object.keys(known);
const $ = (id) => document.getElementById(id);

const dl = $('names');
names.forEach((n) => { const o = document.createElement('option'); o.value = n; dl.appendChild(o); });

function isNew(v) { return v && !(v in known); }

function draw() {
  const f = document.createDocumentFragment();
  DATA.photos.forEach((p, i) => {
    const m = mark[p.f] || {};
    const c = document.createElement('div');
    c.className = 'card' + (m.n ? (isNew(m.n) ? ' neu' : ' done') : '');
    c.innerHTML =
      '<img loading="lazy" decoding="async" src="thumbs/' + p.f + '" alt="" />' +
      '<div class="body">' +
        '<span class="dt"><span>' + (p.d || '沒有日期') + '</span>' +
        (isNew(m.n) ? '<span class="badge">新的花</span>' : '') + '</span>' +
        '<input list="names" placeholder="花名" data-i="' + i + '" />' +
        '<select data-i="' + i + '"></select>' +
      '</div>';
    const inp = c.querySelector('input');
    inp.value = m.n || '';
    const sel = c.querySelector('select');
    sel.innerHTML = '<option value="">選擇區域…</option>' +
      DATA.zones.map((z) => '<option>' + z + '</option>').join('');
    sel.value = m.z || '';
    f.appendChild(c);
  });
  $('g').replaceChildren(f);
  count();
}
function count() {
  const done = DATA.photos.filter((p) => mark[p.f] && mark[p.f].n).length;
  const neu = new Set(DATA.photos.filter((p) => mark[p.f] && isNew(mark[p.f].n)).map((p) => mark[p.f].n));
  $('stat').textContent = '已標 ' + done + ' / ' + DATA.photos.length +
    (neu.size ? '　新的花 ' + neu.size + ' 種' : '');
}
function setName(i, v) {
  const p = DATA.photos[i];
  v = v.trim();
  if (!v) { delete mark[p.f]; }
  else {
    mark[p.f] = Object.assign({}, mark[p.f], { n: v });
    if (v in known) mark[p.f].z = known[v];
  }
  save();
}
$('g').addEventListener('input', (e) => {
  const i = +e.target.dataset.i;
  if (e.target.tagName === 'INPUT') {
    setName(i, e.target.value);
    const card = e.target.closest('.card');
    const v = e.target.value.trim();
    card.className = 'card' + (v ? (isNew(v) ? ' neu' : ' done') : '');
    const b = card.querySelector('.badge');
    if (isNew(v) && !b) card.querySelector('.dt').insertAdjacentHTML('beforeend', '<span class="badge">新的花</span>');
    if (!isNew(v) && b) b.remove();
    const sel = card.querySelector('select');
    if (v in known) sel.value = known[v];
    count();
  } else {
    const p = DATA.photos[i];
    mark[p.f] = Object.assign({}, mark[p.f], { z: e.target.value });
    save();
  }
});
$('g').addEventListener('keydown', (e) => {
  if (e.target.tagName !== 'INPUT') return;
  if (e.key === 'Enter') {
    e.preventDefault();
    const all = [].slice.call(document.querySelectorAll('.card input'));
    const k = all.indexOf(e.target);
    if (all[k + 1]) { all[k + 1].focus(); all[k + 1].scrollIntoView({ block: 'center' }); }
  }
});
document.addEventListener('keydown', (e) => {
  if (e.key !== 's' && e.key !== 'S') return;
  const a = document.activeElement;
  if (a && a.tagName === 'INPUT' && a.value === '') {
    const all = [].slice.call(document.querySelectorAll('.card input'));
    const k = all.indexOf(a);
    for (let j = k - 1; j >= 0; j--) {
      if (all[j].value) {
        e.preventDefault();
        all[k].value = all[j].value;
        all[k].dispatchEvent(new Event('input', { bubbles: true }));
        break;
      }
    }
  }
});
$('same').onclick = () => {
  const all = [].slice.call(document.querySelectorAll('.card input'));
  let last = '';
  all.forEach((inp) => {
    if (inp.value) { last = inp.value; return; }
    if (last) { inp.value = last; inp.dispatchEvent(new Event('input', { bubbles: true })); }
  });
};
$('skipAll').onclick = () => {
  if (!confirm('把還沒標的照片全部標成「不收錄」？這些照片不會進網站。')) return;
  DATA.photos.forEach((p) => { if (!(mark[p.f] && mark[p.f].n)) mark[p.f] = { n: '不收錄' }; });
  save(); draw();
};
$('exp').onclick = () => {
  const out = [];
  DATA.photos.forEach((p) => {
    const m = mark[p.f];
    if (!m || !m.n || m.n === '不收錄') return;
    if (isNew(m.n) && !m.z) { return; }
    out.push({ f: p.f, d: p.d, n: m.n, z: m.z || known[m.n] || '' });
  });
  const missing = DATA.photos.filter((p) => {
    const m = mark[p.f];
    return m && m.n && m.n !== '不收錄' && isNew(m.n) && !m.z;
  });
  if (missing.length) {
    alert('有 ' + missing.length + ' 張新的花還沒選區域，先補上再匯出。');
    return;
  }
  const blob = new Blob([JSON.stringify({ batch: DATA.batch, records: out }, null, 1)],
                        { type: 'application/json' });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = '新增記錄.json';
  a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 3000);
};
$('g').addEventListener('click', (e) => {
  if (e.target.tagName !== 'IMG') return;
  $('lbimg').src = e.target.src.replace('/thumbs/', '/full/');
  $('lb').classList.add('on');
});
$('lb').onclick = () => $('lb').classList.remove('on');
document.addEventListener('keydown', (e) => { if (e.key === 'Escape') $('lb').classList.remove('on'); });
draw();
</script>
</body>
</html>
"""
