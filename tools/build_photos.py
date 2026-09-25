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
    try:
        import pillow_heif                      # 選用：讓 iPhone 的 .HEIC 也能讀
        pillow_heif.register_heif_opener()
    except ImportError:
        pass
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
EXTRA = os.path.expanduser('~/Documents/花曆更新/照片')
EXTS = ('.jpg', '.jpeg', '.png', '.heic', '.heif', '.tif', '.tiff', '.webp')

FB = sys.argv[1].rstrip('/') if len(sys.argv) > 1 else ''
if len(sys.argv) > 2 and sys.argv[2]:
    EXTRA = sys.argv[2].rstrip('/')
if FB and not os.path.isdir(os.path.join(FB, 'posts', 'album')):
    print(f'找不到 {FB}/posts/album，當作沒有 FB 匯出繼續。')
    FB = ''
if not FB and not os.path.isdir(EXTRA):
    print('既沒有 FB 匯出也沒有補充照片，沒事可做。'); sys.exit(0)


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
for f in (sorted(glob.glob(os.path.join(FB, 'posts/album/*.json'))) if FB else []):
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


# 圖說是一整句話時的補救：句首就是花名才算
long_names = sorted((n for n in names if len(n) >= 3), key=len, reverse=True)
for f in (sorted(glob.glob(os.path.join(FB, 'posts/album/*.json'))) if FB else []):
    try:
        d = json.load(open(f, encoding='utf-8'))
    except Exception:
        continue
    if not (isinstance(d, dict) and 'photos' in d):
        continue
    album = fix(d.get('name', ''))
    for p in d['photos']:
        de = fix(p.get('description', '') or '').strip()
        if not de:
            continue
        h = head_name(de)
        if h and alias.get(h, h) in names:
            continue
        hit = next((n for n in long_names if de.startswith(n)), None)
        if not hit:
            continue
        rel = p['uri'].split("this_profile's_activity_across_facebook/", 1)[-1]
        path = os.path.join(FB, rel)
        if not os.path.exists(path) or path in idx.get(hit, {}):
            continue
        ex = (p.get('media_metadata', {}).get('photo_metadata', {}).get('exif_data') or [{}])[0]
        ts = ex.get('taken_timestamp') or p.get('creation_timestamp') or 0
        idx.setdefault(hit, {})[path] = {'ts': ts, 'album': album}

# ---------- 1b. 自己補的照片 ----------
n_extra = 0
if os.path.isdir(EXTRA):
    def shot_time(path):
        """優先用 EXIF 的拍攝時間，沒有才用檔案時間。"""
        try:
            ex = Image.open(path).getexif()
            for tag in (36867, 36868, 306):      # DateTimeOriginal / Digitized / DateTime
                v = ex.get(tag)
                if v:
                    return int(datetime.datetime.strptime(str(v)[:19],
                               '%Y:%m:%d %H:%M:%S').timestamp())
        except Exception:
            pass
        return int(os.path.getmtime(path))

    # 標註工具說過「這張不是花」的檔名（植株／果／葉／其他），挑片時不要排前面
    try:
        PARTS = json.load(open(os.path.join(EXTRA, '.部位.json'), encoding='utf-8'))
    except Exception:
        PARTS = {}
    if PARTS:
        print(f'非花照片 {len(PARTS)} 張（植株／果／葉），不會被選成第一張')

    def add_extra(nm, path):
        global n_extra
        nm = alias.get(nm, nm)
        if nm not in names:
            print(f'  ! 補充照片的花名對不到主檔，略過：{nm}')
            return
        part = PARTS.get(os.path.splitext(os.path.basename(path))[0], '')
        idx.setdefault(nm, {})[path] = {'ts': shot_time(path),
                                        'album': '自己補的' + (f'・{part}' if part else ''),
                                        'own': not part, 'part': part}
        n_extra += 1
    for e in sorted(os.listdir(EXTRA)):
        p = os.path.join(EXTRA, e)
        if os.path.isdir(p):
            for f2 in sorted(os.listdir(p)):
                if f2.lower().endswith(EXTS):
                    add_extra(e.strip(), os.path.join(p, f2))
        elif e.lower().endswith(EXTS):
            add_extra(re.split(r'[-_ ]\d*$|\d+$', os.path.splitext(e)[0])[0].strip(), p)
    print(f'自己補的照片 {n_extra} 張')
else:
    os.makedirs(EXTRA, exist_ok=True)
    print(f'（可以把自己的照片放到 {EXTRA}）')

total = sum(len(v) for v in idx.values())
print(f'對到 {len(idx)} 種花、{total} 張照片')

# --- 保險：不要在找不到來源時把已經做好的照片刪掉 ---
META = os.path.join(ROOT, 'src/photos', SLUG + '.json')
had = len(json.load(open(META, encoding='utf-8'))) if os.path.exists(META) else 0
if total == 0:
    print('找不到任何照片來源，維持原樣不動。')
    sys.exit(0)
if had and len(idx) < had * 0.7 and '--force' not in sys.argv:
    print(f'這次只對到 {len(idx)} 種，原本有 {had} 種，差太多，怕是來源資料夾沒掛好。')
    print('已經停下來，照片維持原樣。確定要覆蓋的話在指令後面加 --force。')
    sys.exit(2)

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
    shutil.rmtree(td, ignore_errors=True)
    os.makedirs(td, exist_ok=True)
    rows = []
    for path, meta in sorted(photos.items(), key=lambda x: -x[1]['ts']):
        k = hashlib.md5(path.encode('utf-8')).hexdigest()[:8]
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
        if meta.get('own'):
            score += 10000          # 自己補的照片一律優先
        elif meta.get('part'):
            score -= 5000           # 植株／果／葉：沒有花的照片可用時才拿來頂
        tn = ImageOps.fit(im, (220, 220), Image.LANCZOS, centering=(.5, .45))
        tn.save(os.path.join(td, f'{k}.jpg'), 'JPEG', quality=58, optimize=True)
        rows.append({'k': k, 'p': path, 'ts': meta['ts'], 'a': meta['album'],
                     'sc': round(score, 1), 'own': bool(meta.get('own')),
                     'd': datetime.date.fromtimestamp(meta['ts']).isoformat() if meta['ts'] else ''})
        done += 1
        if done % 500 == 0:
            print(f'  評分 {done}/{total}  ({time.time()-t0:.0f} 秒)')
    scored[nm] = {'s': sg, 'all': rows}

print(f'評分完成，{done} 張，{time.time()-t0:.0f} 秒')

# ---------- 3. 決定每種用哪 4 張 ----------
picks_file = os.path.join(ROOT, 'tools/photo_picks.json')
manual = json.load(open(picks_file, encoding='utf-8')) if os.path.exists(picks_file) else {}

# 舊版的手動指定是「第幾張」，照片一增減就會對到別張。這裡換算成固定編號，只做一次。
if any(isinstance(v, list) and v and isinstance(v[0], int) for v in manual.values()):
    conv, drop = {}, []
    for nm, want in manual.items():
        rows = scored.get(nm, {}).get('all', [])
        if not rows:
            continue
        if not (want and isinstance(want[0], int)):
            conv[nm] = want; continue
        if any(r.get('own') for r in rows):
            drop.append(nm); continue          # 有自己補的照片，順序已變，交給自動挑選
        got = [rows[i]['k'] for i in want if 0 <= i < len(rows)]
        if got:
            conv[nm] = got
    shutil.copy2(picks_file, picks_file + '.bak')
    json.dump(conv, open(picks_file, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    manual = conv
    print(f'手動指定已換成固定編號（舊檔備份為 photo_picks.json.bak）')
    if drop:
        print(f'  這幾種有自己補的照片，順序變了，改用自動挑選，請重新挑一次：{"、".join(drop)}')

print(f'手動指定 {len(manual)} 種')


def auto_pick(rows):
    """自己補的照片一律優先；其餘按分數，同一天最多取一張，湊不滿再放寬。"""
    out = [r for r in rows if r.get('own')][:N_PICK]
    seen = set()
    for r in sorted((r for r in rows if not r.get('own')), key=lambda r: -r['sc']):
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
if len(sys.argv) <= 2:
    print('\n完成。接著執行：')
    print('  npm run build && git add -A && git commit -m "加上照片" && git push')
