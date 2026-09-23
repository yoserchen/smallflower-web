#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
小花老師的花曆 — 照片處理

用法（在 smallflower-web 資料夾裡執行）：
    python3 tools/build_photos.py "/Users/chenqingyu/Downloads/this_profile's_activity_across_facebook 2"

做三件事：
  1. 掃描 FB 匯出的所有照片，用圖說對到花名
  2. 自動評分挑出每種花最好的 4 張，做成網站用的圖，寫到 public/p/
  3. 另外做一份「挑片工具」到 ~/Documents/花曆挑片/，可以自己換照片

如果 tools/photo_picks.json 存在（挑片工具匯出的檔案），那些花會照你挑的來，
其餘的才用自動評分。
"""
import os, sys, json, glob, hashlib, datetime, shutil, re, time

try:
    from PIL import Image, ImageOps, ImageFilter, ImageStat
except ImportError:
    print("""
少了 Pillow 這個套件。請先執行下面這行安裝，再重跑一次：

    pip3 install --user pillow

如果出現 externally-managed-environment 的錯誤，改用：

    pip3 install --user --break-system-packages pillow
""")
    sys.exit(1)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SLUG = 'tpbg'
N_PICK = 4
PICKER = os.path.expanduser('~/Documents/花曆挑片')

if len(sys.argv) < 2:
    print('用法：python3 tools/build_photos.py "<FB 匯出資料夾>"'); sys.exit(1)
FB = sys.argv[1].rstrip('/')
if not os.path.isdir(os.path.join(FB, 'posts', 'album')):
    print('找不到 posts/album，請確認路徑是解壓後那個 this_profile.. 資料夾'); sys.exit(1)


def fix(s):
    if not isinstance(s, str):
        return s
    try:
        return s.encode('latin-1').decode('utf-8')
    except Exception:
        return s


def head_name(desc):
    if not desc:
        return None
    d = desc.strip().replace('　', ' ')
    h = re.split(r'[：:，,\n]', d)[0].strip()
    h = re.sub(r'[（(].*?[)）]', '', h).strip()
    h = re.sub(r'\s+.*$', '', h).strip()
    return h or None


def slugify(n):
    return hashlib.md5(n.encode('utf-8')).hexdigest()[:10]


# ---------- 1. 建立索引 ----------
species = json.load(open(os.path.join(ROOT, 'src/data', SLUG + '.json'), encoding='utf-8'))
names = {s['n'] for s in species}
alias = json.load(open(os.path.join(ROOT, 'tools/aliases.json'), encoding='utf-8'))

idx = {}
for f in sorted(glob.glob(os.path.join(FB, 'posts/album/*.json'))):
    try:
        d = json.load(open(f, encoding='utf-8'))
    except Exception:
        continue
    if not (isinstance(d, dict) and 'photos' in d):
        continue
    album = fix(d.get('name', ''))
    for p in d['photos']:
        nm = head_name(fix(p.get('description', '')))
        if not nm:
            continue
        nm = alias.get(nm, nm)
        if nm not in names:
            continue
        rel = p['uri'].split("this_profile's_activity_across_facebook/", 1)[-1]
        path = os.path.join(FB, rel)
        if not os.path.exists(path):
            continue
        ex = (p.get('media_metadata', {}).get('photo_metadata', {}).get('exif_data') or [{}])[0]
        ts = ex.get('taken_timestamp') or p.get('creation_timestamp') or 0
        idx.setdefault(nm, {})[path] = {'ts': ts, 'album': album}

total = sum(len(v) for v in idx.values())
print(f'對到 {len(idx)} 種花、{total} 張照片')

# ---------- 2. 評分 + 做挑片縮圖 ----------
os.makedirs(PICKER, exist_ok=True)
THUMBS = os.path.join(PICKER, 'thumbs')
os.makedirs(THUMBS, exist_ok=True)

scored = {}
done = 0
t0 = time.time()
for nm, photos in sorted(idx.items()):
    sg = slugify(nm)
    td = os.path.join(THUMBS, sg)
    os.makedirs(td, exist_ok=True)
    rows = []
    for k, (path, meta) in enumerate(sorted(photos.items(), key=lambda x: -x[1]['ts'])):
        try:
            im = Image.open(path)
            im.draft('RGB', (640, 640))          # JPEG 快速降尺寸解碼
            im = ImageOps.exif_transpose(im).convert('RGB')
        except Exception:
            continue
        g = im.convert('L')
        g.thumbnail((360, 360), Image.BILINEAR)
        # 銳利度：邊緣強度的變異
        e = g.filter(ImageFilter.FIND_EDGES)
        sharp = ImageStat.Stat(e).stddev[0]
        # 主體：中央區域比整體亮度對比（特寫通常中央變化大）
        w, h = g.size
        c = g.crop((w // 4, h // 4, w * 3 // 4, h * 3 // 4))
        center = ImageStat.Stat(c).stddev[0]
        yr = datetime.date.fromtimestamp(meta['ts']).year if meta['ts'] else 2023
        score = sharp * 1.0 + center * 0.6 + max(0, yr - 2023) * 3.0
        tn = ImageOps.fit(im, (220, 220), Image.LANCZOS, centering=(.5, .45))
        tn.save(os.path.join(td, f'{k}.jpg'), 'JPEG', quality=58, optimize=True)
        rows.append({'k': k, 'p': path, 'ts': meta['ts'], 'a': meta['album'],
                     'sc': round(score, 1),
                     'd': datetime.date.fromtimestamp(meta['ts']).isoformat() if meta['ts'] else ''})
        done += 1
        if done % 500 == 0:
            print(f'  評分 {done}/{total}  ({time.time()-t0:.0f} 秒)')
    scored[nm] = {'s': sg, 'all': rows}

print(f'評分完成，{done} 張，{time.time()-t0:.0f} 秒')

# ---------- 3. 決定每種用哪 4 張 ----------
picks_file = os.path.join(ROOT, 'tools/photo_picks.json')
manual = json.load(open(picks_file, encoding='utf-8')) if os.path.exists(picks_file) else {}
print(f'手動指定 {len(manual)} 種')


def auto_pick(rows):
    """分數排序，但同一天最多取一張，湊不滿再放寬。"""
    out, seen = [], set()
    for r in sorted(rows, key=lambda r: -r['sc']):
        if len(out) >= N_PICK:
            break
        if r['d'] and r['d'] in seen:
            continue
        seen.add(r['d']); out.append(r)
    if len(out) < N_PICK:
        for r in sorted(rows, key=lambda r: -r['sc']):
            if len(out) >= N_PICK:
                break
            if r not in out:
                out.append(r)
    return out


# ---------- 4. 產生網站用圖 ----------
PUB = os.path.join(ROOT, 'public/p')
if os.path.isdir(PUB):
    shutil.rmtree(PUB)
os.makedirs(PUB)

meta_out = {}
nfiles = 0
t0 = time.time()
for nm, info in sorted(scored.items()):
    rows = info['all']
    if not rows:
        continue
    if nm in manual:
        want = manual[nm]
        chosen = [r for k in want for r in rows if r['k'] == k][:N_PICK]
        if not chosen:
            chosen = auto_pick(rows)
    else:
        chosen = auto_pick(rows)
    d = os.path.join(PUB, info['s'])
    os.makedirs(d, exist_ok=True)
    items = []
    for i, r in enumerate(chosen, 1):
        try:
            im = Image.open(r['p'])
            im = ImageOps.exif_transpose(im).convert('RGB')
        except Exception:
            continue
        big = im.copy()
        big.thumbnail((1280, 1280), Image.LANCZOS)
        big.save(f'{d}/{i}.jpg', 'JPEG', quality=78, optimize=True, progressive=True)
        th = ImageOps.fit(im, (480, 480), Image.LANCZOS, centering=(.5, .45))
        th.save(f'{d}/{i}t.jpg', 'JPEG', quality=72, optimize=True)
        items.append({'i': i, 'd': r['d'], 'a': r['a']})
        nfiles += 2
    if items:
        meta_out[nm] = {'s': info['s'], 'ph': items}

os.makedirs(os.path.join(ROOT, 'src/photos'), exist_ok=True)
json.dump(meta_out, open(os.path.join(ROOT, 'src/photos', SLUG + '.json'), 'w', encoding='utf-8'),
          ensure_ascii=False, separators=(',', ':'))

size = sum(os.path.getsize(os.path.join(dp, f))
           for dp, _, fs in os.walk(PUB) for f in fs)
print(f'網站圖完成：{len(meta_out)} 種、{nfiles} 個檔案、{size/1e6:.0f} MB、{time.time()-t0:.0f} 秒')

# ---------- 5. 挑片工具索引 ----------
pick_idx = {nm: {'s': v['s'],
                 'n': len(v['all']),
                 'ph': [{'k': r['k'], 'd': r['d'], 'a': r['a']} for r in v['all']]}
            for nm, v in scored.items() if v['all']}
current = {nm: [r['k'] for r in
                ([x for k in manual[nm] for x in scored[nm]['all'] if x['k'] == k]
                 if nm in manual else auto_pick(scored[nm]['all']))]
           for nm in pick_idx}
blob = json.dumps({'species': pick_idx, 'current': current},
                  ensure_ascii=False, separators=(',', ':'))

sys.path.insert(0, os.path.join(ROOT, 'tools'))
from picker_tpl import PICKER_HTML  # noqa: E402
html = PICKER_HTML.replace('__DATA__', blob)
with open(os.path.join(PICKER, '挑片.html'), 'w', encoding='utf-8') as fh:
    fh.write(html)

print(f'挑片工具寫到 {PICKER}/挑片.html（{len(pick_idx)} 種）')
print('\n完成。接著執行：')
print('  npm run build && git add -A && git commit -m "加上照片" && git push')
