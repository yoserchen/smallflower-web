#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
小花老師的花曆 — 一次更新全部

用法（在 smallflower-web 資料夾裡執行）：
    python3 tools/update.py

它會去 ~/Documents/花曆更新/ 找這些東西，有就用新的，沒有就沿用上次的：

    花曆更新/
    ├── 主檔.xlsx            從 Google 試算表下載（檔案 → 下載 → Excel）
    ├── 地圖/*.kml           從 My Maps 匯出
    ├── 照片/<花名>/*.jpg    自己補的照片
    ├── 待標註/              這個月拍的照片，先跑 tools/label.py 標花名
    ├── 新增記錄.json        標註工具匯出的檔案，會自動收進觀測記錄
    └── FB匯出/              解壓後的 this_profile.. 資料夾（或捷徑）

每個月的流程：
    1. 把這個月的照片放進 待標註/
    2. python3 tools/label.py          → 打開 ~/Documents/花曆標註/標註.html 標花名
    3. 匯出的 新增記錄.json 放到 花曆更新/
    4. python3 tools/update.py
    5. npm run build && git add -A && git commit -m "更新" && git push

跑完之後：
    npm run build && git add -A && git commit -m "更新" && git push
"""
import os, sys, csv, json, glob, re, shutil, subprocess, collections, datetime, time
import xml.etree.ElementTree as ET

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, 'tools/data')          # 上次用過的基準檔
IN = os.path.expanduser('~/Documents/花曆更新')
SLUG = 'tpbg'
CUTOFF = '2025-09-21'                            # 這天之後拍到才算「現存」
ZONE_RENAME = {'蜜源植物區': '植物與昆蟲區', '名人植物區': '植物名人園區'}

sys.path.insert(0, os.path.join(ROOT, 'tools'))


def say(s=''):
    print(s, flush=True)


# ---------- 準備輸入資料夾 ----------
if not os.path.isdir(IN):
    for sub in ('地圖', '照片'):
        os.makedirs(os.path.join(IN, sub), exist_ok=True)
    with open(os.path.join(IN, '說明.txt'), 'w', encoding='utf-8') as f:
        f.write(__doc__)
    say(f'已經建好 {IN}，把要更新的東西放進去再執行一次。')

os.makedirs(DATA, exist_ok=True)


def newest(pattern, fallback_dir, fallback_pattern):
    """先找更新資料夾，沒有就用上次存的基準檔。回傳 (檔案清單, 是不是新的)"""
    got = sorted(glob.glob(pattern))
    if got:
        return got, True
    return sorted(glob.glob(os.path.join(fallback_dir, fallback_pattern))), False


# ---------- 1. 主檔 ----------
xl, xl_new = newest(os.path.join(IN, '*.xlsx'), DATA, '主檔.xlsx')
if not xl:
    say('找不到主檔.xlsx。請從 Google 試算表下載（檔案 → 下載 → Microsoft Excel），')
    say(f'放到 {IN}/ 底下，再執行一次。')
    sys.exit(1)
# 資料夾裡有好幾個 xlsx 時，用最近下載的那一個（不要挑到上次的舊檔）
MASTER = max(xl, key=os.path.getmtime)
say(f'主檔：{os.path.basename(MASTER)}' + ('　（新的）' if xl_new else '　（沿用上次）'))
if len(xl) > 1:
    say('　（資料夾裡有 ' + str(len(xl)) + ' 個 xlsx，用了最新的這個；舊的建議刪掉）')

from openpyxl import load_workbook                                    # noqa: E402
wb = load_workbook(MASTER, data_only=True)
if '物種主檔' not in wb.sheetnames:
    say('這個 xlsx 裡沒有「物種主檔」工作表，請確認下載的是對的檔案。'); sys.exit(1)

# ---------- 2. 名稱對照表 ----------
RULES_CSV = os.path.join(DATA, '名稱對照表.csv')
rules = {r['原名稱']: r for r in csv.DictReader(open(RULES_CSV, encoding='utf-8-sig'))}
# 主檔自己的「名稱對照表」分頁如果比較新，以它為準
if '名稱對照表' in wb.sheetnames:
    it = wb['名稱對照表'].iter_rows(values_only=True)
    hdr = list(next(it))
    if hdr and hdr[0] == '原名稱':
        got = {}
        for r in it:
            if r and r[0]:
                got[str(r[0]).strip()] = {'原名稱': str(r[0]).strip(),
                                          '處理方式': (r[1] or '').strip(),
                                          '併入': (r[2] or '').strip(),
                                          '原因': (r[3] or '').strip()}
        if len(got) > len(rules):
            rules = got
            with open(RULES_CSV, 'w', encoding='utf-8-sig', newline='') as f:
                w = csv.DictWriter(f, fieldnames=['原名稱', '處理方式', '併入', '原因'])
                w.writeheader(); w.writerows(rules.values())
            say(f'名稱對照表改用主檔裡的版本（{len(rules)} 條）')
say(f'名稱對照表：{len(rules)} 條')


def canon(n):
    seen = set()
    while n in rules and rules[n]['處理方式'] == '合併' and n not in seen:
        seen.add(n); n = rules[n]['併入']
    return n


# ---------- 2b. 收進標註工具產出的新記錄 ----------
OBS_CSV = os.path.join(DATA, '觀測記錄.csv')
OBS_COLS = ['花名', '日期', '區域', '檔名', '部位', '緯度', '經度']
obs_rows = list(csv.DictReader(open(OBS_CSV, encoding='utf-8-sig'))) if os.path.exists(OBS_CSV) else []
seen_files = {r['檔名'] for r in obs_rows}
PHOTO_DIR = os.path.join(IN, '照片')
PENDING = os.path.join(IN, '待標註')
added = 0
for jf in sorted(glob.glob(os.path.join(IN, '新增記錄*.json'))):
    try:
        got = json.load(open(jf, encoding='utf-8'))
    except Exception as e:
        say(f'  ! 讀不了 {os.path.basename(jf)}：{e}'); continue
    for r in got.get('records', []):
        nm, d, z, fn = r.get('n', '').strip(), r.get('d', ''), r.get('z', '').strip(), r.get('f', '')
        if not nm or not d or fn in seen_files:
            continue
        obs_rows.append({'花名': nm, '日期': d, '區域': z, '檔名': fn,
                         '部位': (r.get('t') or '花').strip() or '花',
                         '緯度': r.get('lat', ''), '經度': r.get('lon', '')})
        seen_files.add(fn); added += 1
        # 把照片搬到該花的資料夾，之後就跟自己補的照片一樣處理
        base = os.path.splitext(fn)[0]
        src = next((os.path.join(PENDING, f) for f in (os.listdir(PENDING) if os.path.isdir(PENDING) else [])
                    if os.path.splitext(f)[0] == base), None)
        if src and os.path.exists(src):
            dst = os.path.join(PHOTO_DIR, canon(nm))
            os.makedirs(dst, exist_ok=True)
            try:
                shutil.move(src, os.path.join(dst, os.path.basename(src)))
            except Exception as e:
                say(f'  ! 搬不動 {os.path.basename(src)}：{e}')
    os.makedirs(os.path.join(DATA, '已匯入'), exist_ok=True)
    shutil.move(jf, os.path.join(DATA, '已匯入',
                datetime.datetime.now().strftime('%Y%m%d_%H%M%S_') + os.path.basename(jf)))
if added:
    with open(OBS_CSV, 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=OBS_COLS); w.writeheader(); w.writerows(obs_rows)
    say(f'新記錄 {added} 筆已收進觀測記錄')
if obs_rows:
    nf = sum(1 for r in obs_rows if (r.get('部位') or '花') != '花')
    say(f'觀測記錄累計 {len(obs_rows)} 筆' + (f'（其中 {nf} 筆非花，不算開花月份）' if nf else ''))
    # 給 build_photos.py 看的小抄：這些檔名不是花，挑照片時不要優先
    os.makedirs(PHOTO_DIR, exist_ok=True)
    # 用去掉副檔名的檔名當鍵：標註工具記的是 .jpg，歸檔的可能還是 .HEIC
    json.dump({os.path.splitext(r['檔名'])[0]: r['部位'] for r in obs_rows
               if r.get('檔名') and (r.get('部位') or '花') != '花'},
              open(os.path.join(PHOTO_DIR, '.部位.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=0)

# 整理成「花名 -> 月份、筆數、最後拍到、區域」
obs = {}
for r in obs_rows:
    cn = canon(r['花名'].strip())
    d = r['日期'].strip()
    if len(d) < 7:
        continue
    o = obs.setdefault(cn, {'months': set(), 'n': 0, 'last': '', 'zone': '',
                            'll': None, 'parts': set()})
    part = (r.get('部位') or '花').strip() or '花'
    o['parts'].add(part)
    # 只有「花」才算開花月份與記錄數；植株、果、葉只是照片
    if part == '花':
        o['months'].add(int(d[5:7])); o['n'] += 1
    o['last'] = max(o['last'], d)
    if r['區域'].strip():
        o['zone'] = ZONE_RENAME.get(r['區域'].strip(), r['區域'].strip())
    try:
        if r.get('緯度') and r.get('經度'):
            o['ll'] = (float(r['緯度']), float(r['經度']))
    except (TypeError, ValueError):
        pass

# 「記錄部位」欄的意思是「除了花，還拍到什麼」。植株、其他只是照片屬性，不寫進這一欄，
# 不然一朵拍過花的花會變成只寫「植株」，看起來像沒拍到花。
PART_IN_MASTER = {'果', '葉'}

EXCL = {n for n, r in rules.items() if r['處理方式'] == '不收錄'}
MAPX = {n for n, r in rules.items() if r['處理方式'] in ('地圖不收錄', '地圖不放')}
json.dump({n: canon(n) for n, r in rules.items() if r['處理方式'] == '合併'},
          open(os.path.join(ROOT, 'tools/aliases.json'), 'w'), ensure_ascii=False, indent=0)

# ---------- 3. 地圖 KML ----------
kmls, kml_new = newest(os.path.join(IN, '地圖/*.kml'), os.path.join(DATA, 'kml'), '*.kml')
say(f'地圖 KML：{len(kmls)} 個檔' + ('　（新的）' if kml_new else '　（沿用上次）'))

NS = '{http://www.opengis.net/kml/2.2}'
pins = collections.defaultdict(list)       # 內部代號 -> [(lat, lon)]
loose = []                                 # 沒有編號的圖釘 [(名稱, lat, lon)]
for f in kmls:
    try:
        root = ET.parse(f).getroot()
    except Exception as e:
        say(f'  ! 讀不了 {os.path.basename(f)}：{e}'); continue
    for p in root.iter(NS + 'Placemark'):
        nm = (p.findtext(NS + 'name') or '').strip()
        m = re.match(r'(\S+?-\d+)', nm)
        c = p.find('.//' + NS + 'coordinates')
        if c is None or not c.text:
            continue
        try:
            lo, la = c.text.strip().split(',')[:2]
            la, lo = float(la), float(lo)
        except Exception:
            continue
        if m:
            pins[m.group(1)].append((la, lo))
        elif nm and p.find('.//' + NS + 'Point') is not None:
            loose.append((nm, la, lo))      # 線和面（步道、道路、區域範圍）不算
say(f'　讀到 {sum(len(v) for v in pins.values())} 個點、{len(pins)} 個代號'
    + (f'，另外有 {len(loose)} 個沒編號的點' if loose else ''))

# 保險：新匯出的 KML 如果點數明顯變少，多半是只匯出了一個圖層
BASE_KML = os.path.join(DATA, 'kml')
if kml_new:
    prev = 0
    for f in glob.glob(os.path.join(BASE_KML, '*.kml')):
        try:
            prev += sum(1 for _ in ET.parse(f).getroot().iter(NS + 'Placemark'))
        except Exception:
            pass
    now = sum(len(v) for v in pins.values())
    if prev and now < prev * 0.8 and '--force' not in sys.argv:
        say(f'  ! 新的 KML 只有 {now} 個點，上次有 {prev} 個，少了超過兩成。')
        say('    My Maps 匯出時要選「整張地圖」而不是單一圖層。')
        say('    已經停下來，沒有改動任何資料。確定要用的話在指令後面加 --force。')
        sys.exit(2)

# ---------- 3b. 沒有編號的圖釘：同一種花的另一個位置 ----------
# 在 My Maps 直接加一個點、名稱打花名就好，這裡會自動配一個內部代號，
# 並且把代號記在 tools/data/圖釘編號.csv，之後每次都認得同一個點。
PIN_CSV = os.path.join(DATA, '圖釘編號.csv')
PIN_COLS = ['內部代號', '中文名', '緯度', '經度']
remembered = list(csv.DictReader(open(PIN_CSV, encoding='utf-8-sig'))) \
    if os.path.exists(PIN_CSV) else []
extra_rows = []


def metres(a, b):
    import math
    dy = (a[0] - b[0]) * 111320
    dx = (a[1] - b[1]) * 111320 * math.cos(math.radians(a[0]))
    return (dx * dx + dy * dy) ** .5


if loose:
    # 先從主檔讀出：代號 -> (中文名, 區域)，以及每一區慣用的代號前綴與目前最大號
    m_name, m_zone, zpre, pmax = {}, {}, {}, collections.Counter()
    it0 = wb['物種主檔'].iter_rows(values_only=True)
    h0 = [str(x).strip() if x else '' for x in next(it0)]
    c0 = {k: i for i, k in enumerate(h0)}
    all_names = set()
    for r0 in it0:
        if not r0 or not r0[c0['內部代號']]:
            continue
        cd = str(r0[c0['內部代號']]).strip()
        nm0 = str(r0[c0['中文名']] or '').strip()
        z0 = str(r0[c0['區域']] or '').strip()
        z0 = ZONE_RENAME.get(z0, z0)
        m_name[cd] = nm0; m_zone[cd] = z0; all_names.add(canon(nm0))
        mm = re.match(r'(.+)-(\d+)$', cd)
        if mm:
            pre, num = mm.group(1), int(mm.group(2))
            pmax[pre] = max(pmax[pre], num)
            if z0:
                zpre.setdefault(z0, collections.Counter())[pre] += 1
    # 已經配過號的也要算進最大號，免得撞號
    for r0 in remembered:
        mm = re.match(r'(.+)-(\d+)$', r0['內部代號'])
        if mm:
            pmax[mm.group(1)] = max(pmax[mm.group(1)], int(mm.group(2)))

    ref = [(la, lo, m_zone[cd]) for cd, qs in pins.items() if m_zone.get(cd)
           for la, lo in qs]

    def zone_at(la, lo, k=9):
        if not ref:
            return ''
        near = sorted(ref, key=lambda r: metres((la, lo), (r[0], r[1])))[:k]
        return collections.Counter(r[2] for r in near).most_common(1)[0][0]

    say()
    for nm0, la, lo in loose:
        cn0 = canon(re.sub(r'^[\W_]+', '', nm0).strip())
        if cn0 not in all_names:
            say(f'  ! 沒編號的點「{nm0}」對不到主檔裡的花名，先跳過')
            continue
        hit = None
        for r0 in remembered:
            if r0['中文名'] == cn0 and \
                    metres((la, lo), (float(r0['緯度']), float(r0['經度']))) < 60:
                hit = r0; break
        if hit:
            hit['緯度'], hit['經度'] = f'{la:.7f}', f'{lo:.7f}'   # 記住新位置
            code = hit['內部代號']
        else:
            z0 = zone_at(la, lo)
            pre = (zpre.get(z0).most_common(1)[0][0] if zpre.get(z0) else '新')
            pmax[pre] += 1
            code = f'{pre}-{pmax[pre]:02d}'
            remembered.append({'內部代號': code, '中文名': cn0,
                               '緯度': f'{la:.7f}', '經度': f'{lo:.7f}'})
            extra_rows.append({'內部代號': code, '中文名': cn0, '區域': z0,
                               '備註': '同一種花的另一個位置；月份與記錄數留空'})
            say(f'  沒編號的點「{cn0}」配到新代號 {code}（{z0 or "區域判斷不出來"}）')
        pins[code].append((la, lo))
    with open(PIN_CSV, 'w', encoding='utf-8-sig', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=PIN_COLS); w.writeheader(); w.writerows(remembered)
    if extra_rows:
        say(f'　這 {len(extra_rows)} 個代號等一下會寫進「新增物種_待貼到主檔.csv」')
    say(f'　圖釘編號表：{len(remembered)} 筆（{PIN_CSV}）')

# ---------- 4. 溫室 / 蘭房 ----------
indoor = {}
OSM = os.path.join(DATA, 'map.osm')
if os.path.exists(OSM) and pins:
    osm = ET.parse(OSM).getroot()
    N = {n.get('id'): (float(n.get('lat')), float(n.get('lon'))) for n in osm.findall('node')}
    W = {w.get('id'): [N[x.get('ref')] for x in w.findall('nd') if x.get('ref') in N]
         for w in osm.findall('way')}

    def tags(e):
        return {x.get('k'): x.get('v') for x in e.findall('tag')}

    def rings(rel):
        segs = [W[m.get('ref')][:] for m in rel.findall('member')
                if m.get('type') == 'way' and m.get('role') in ('outer', '') and m.get('ref') in W]
        out = []
        while segs:
            ring = segs.pop(0); ch = True
            while ch and ring and ring[0] != ring[-1]:
                ch = False
                for i, s in enumerate(segs):
                    if s and s[0] == ring[-1]:
                        ring += s[1:]; segs.pop(i); ch = True; break
                    if s and s[-1] == ring[-1]:
                        ring += s[::-1][1:]; segs.pop(i); ch = True; break
            out.append(ring)
        return out

    lanfang = [W[w.get('id')] for w in osm.findall('way') if tags(w).get('name') == '蘭房']
    big = [g for rel in osm.findall('relation') if tags(rel).get('building') == 'roof'
           for g in rings(rel) if len(g) > 3]

    def inside(p, poly):
        y, x = p; c = False
        for i in range(len(poly)):
            y1, x1 = poly[i]; y2, x2 = poly[(i + 1) % len(poly)]
            if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
                c = not c
        return c

    for code, qs in pins.items():
        for q in qs:
            lab = '蘭房' if any(inside(q, g) for g in lanfang) else (
                  '溫室' if any(inside(q, g) for g in big) else None)
            if lab:
                indoor.setdefault(code, set()).add(lab)
    say(f'　室內：溫室/蘭房共 {len(indoor)} 個代號')

# ---------- 5. 印刷編號 ----------
pnum = {}
PN = os.path.join(DATA, '印刷編號.csv')
if os.path.exists(PN):
    for r in csv.DictReader(open(PN, encoding='utf-8-sig')):
        if r.get('印刷編號'):
            pnum[r['內部代號']] = r['印刷編號'].split('、')

# ---------- 6. 組出物種資料 ----------
rows = []
it = wb['物種主檔'].iter_rows(values_only=True)
hdr = [str(x).strip() if x else '' for x in next(it)]
col = {h: i for i, h in enumerate(hdr)}


def g(r, name, default=''):
    i = col.get(name)
    return default if i is None or i >= len(r) or r[i] is None else r[i]


need = ['內部代號', '中文名', '狀態修正', '自動開花月份', '月份修正', '最後拍到',
        '拍到年份', '記錄數', '區域', '記錄部位']
missing = [n for n in need if n not in col]
if missing:
    say('主檔少了這些欄位：' + '、'.join(missing)); sys.exit(1)
NOTE_COL = '說明' if '說明' in col else ('備註' if '備註' in col else None)
if NOTE_COL:
    say(f'花的說明文字取自「{NOTE_COL}」欄')

for r in it:
    if not r or not g(r, '內部代號'):
        continue
    z = str(g(r, '區域')).strip()
    rows.append(dict(id=str(g(r, '內部代號')).strip(), n=str(g(r, '中文名')).strip(),
                     fix=str(g(r, '狀態修正')).strip(), months=g(r, '自動開花月份'),
                     mfix=str(g(r, '月份修正')).strip(), last=g(r, '最後拍到'),
                     years=g(r, '拍到年份'), c=g(r, '記錄數', 0) or 0,
                     zone=ZONE_RENAME.get(z, z), parts=g(r, '記錄部位'),
                     up=str(g(r, '上地圖')).strip() != '否',
                     note=str(g(r, NOTE_COL)).strip() if NOTE_COL else ''))
n_off = sum(1 for r in rows if not r['up'])
say(f'主檔 {len(rows)} 列' + (f'，其中 {n_off} 列「上地圖」是否，不給地圖編號' if n_off else ''))

groups = collections.defaultdict(list)
for r in rows:
    groups[canon(r['n'])].append(r)

out, dropped = [], []
for cn, g in groups.items():
    if cn in EXCL:
        dropped.append((cn, '名稱對照表 不收錄')); continue
    # 標成「不收錄」的是那一列，不是整種花。同名的其他列還在就留著。
    g = [r for r in g if r['fix'] != '不收錄']
    if not g:
        dropped.append((cn, '主檔 不收錄')); continue
    fixes = [r['fix'] for r in g if r['fix']]
    # 代表列：同名的好幾列裡，用記錄數最多的那一列（它的區域最可信）
    same = [r for r in g if r['n'] == cn] or g
    rep = max(same, key=lambda r: (r['c'], r['last'] or ''))
    months, years, parts, nos, ind = set(), set(), set(), [], set()
    cnt, last = 0, ''
    for r in g:
        src = r['mfix'] or r['months']
        months |= {int(x) for x in str(src).replace('，', ',').split(',') if x.strip().isdigit()}
        years |= {int(x) for x in str(r['years']).split() if x.strip().isdigit()}
        cnt += r['c']; last = max(last, r['last'] or '')
        if r['parts']:
            parts |= set(str(r['parts']).split('、'))
        if r['up']:
            nos += pnum.get(r['id'], [])
        ind |= indoor.get(r['id'], set())
        if r['id'] in pins:
            pass
    o = obs.get(cn)
    if o:
        months |= o['months']
        parts |= o['parts'] & PART_IN_MASTER
        cnt += o['n']
        last = max(str(last), o['last'])
        years |= {int(o['last'][:4])}
    has_pin = any(r['id'] in pins for r in g)
    st = rep['fix'] or (fixes[0] if fixes else '') or \
        ('現存' if (str(last) >= CUTOFF or has_pin) else '近年未見')
    onmap = st == '現存' and cn not in MAPX

    def key(x):
        try:
            return tuple(int(v) for v in x.split('-'))
        except Exception:
            return (9, 9999)
    note = next((r['note'] for r in g if r.get('note')), '')
    rec = dict(id=rep['id'], n=cn, m=sum(1 << (k - 1) for k in months),
               y=sum(1 << (k - 2023) for k in years if 2023 <= k <= 2026),
               c=cnt, last=str(last), st=st,
               no=sorted(set(nos), key=key) if onmap else [],
               z=rep['zone'], p='、'.join(sorted(parts)), i='、'.join(sorted(ind)))
    others = sorted({r['zone'] for r in g if r['zone'] and r['zone'] != rep['zone']})
    if others:
        rec['zz'] = others
    if note:
        rec['t'] = note
    out.append(rec)
# ---------- 6b. 觀測記錄裡出現、主檔還沒有的花 ----------
# 每一區的代號前綴與目前最大號，用來配新代號
zone_prefix, prefix_max = {}, collections.Counter()
for r in rows:
    m = re.match(r'(.+)-(\d+)$', r['id'])
    if not m:
        continue
    pre, num = m.group(1), int(m.group(2))
    prefix_max[pre] = max(prefix_max[pre], num)
    if r['zone']:
        zone_prefix.setdefault(r['zone'], collections.Counter())[pre] += 1

for r0 in remembered:                      # 3b 已經配掉的號不要再用
    mm = re.match(r'(.+)-(\d+)$', r0['內部代號'])
    if mm:
        prefix_max[mm.group(1)] = max(prefix_max[mm.group(1)], int(mm.group(2)))

have = {x['n'] for x in out}
fresh = []
for cn, o in sorted(obs.items()):
    if cn in have or cn in EXCL:
        continue
    z = o['zone']
    pre = (zone_prefix.get(z).most_common(1)[0][0] if zone_prefix.get(z) else '新')
    prefix_max[pre] += 1
    code = f'{pre}-{prefix_max[pre]:02d}'
    yr = int(o['last'][:4])
    out.append(dict(id=code, n=cn, m=sum(1 << (k - 1) for k in o['months']),
                    y=sum(1 << (k - 2023) for k in [yr] if 2023 <= k <= 2026),
                    c=o['n'], last=o['last'], st='現存', no=[], z=z,
                    p='、'.join(sorted(o['parts'] & PART_IN_MASTER)), i=''))
    fresh.append({'內部代號': code, '中文名': cn, '區域': z,
                  '備註': ('新的花；開花月份與記錄數由觀測記錄自動帶入，這兩欄請留空'
                           if o['months'] else
                           '新的花；目前只有植株／果葉照，還沒拍到花，開花月份先留空'),
                  '_月份': ','.join(str(x) for x in sorted(o['months'])) or '（還沒拍到花）'})
    have.add(cn)

if fresh or extra_rows:
    say()
if fresh:
    say(f'觀測記錄帶出 {len(fresh)} 種主檔還沒有的花：')
    for f2 in fresh:
        mm = f2['_月份']
        say(f"　{f2['內部代號']}　{f2['中文名']}　{f2['區域']}　" + (mm if mm.startswith('（') else mm + ' 月'))

if fresh or extra_rows:
    nf = os.path.join(IN, '新增物種_待貼到主檔.csv')
    with open(nf, 'w', encoding='utf-8-sig', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=['內部代號', '中文名', '區域', '備註'],
                           extrasaction='ignore')
        w.writeheader(); w.writerows(fresh + extra_rows)
    say(f'清單寫到 {nf}（{len(fresh)} 種新的花、{len(extra_rows)} 個新位置），'
        '可以貼進 Google 試算表的物種主檔')
    say('　（只貼代號、中文名、區域三欄，月份和記錄數留空，那兩欄會自動算）')
else:
    old_nf = os.path.join(IN, '新增物種_待貼到主檔.csv')
    if os.path.exists(old_nf):
        os.remove(old_nf)          # 上次的已經貼過了，刪掉免得又貼一次

if fresh:
    # 待定位 KML：先放在該區中心，匯入 My Maps 之後把點拖到正確位置
    zf = os.path.join(ROOT, 'src/zones', SLUG + '.json')
    centres = json.load(open(zf, encoding='utf-8')) if os.path.exists(zf) else {}
    pts, n_gps = [], 0
    for f2 in fresh:
        ll = obs.get(f2['中文名'], {}).get('ll')
        if ll:
            pts.append((f2, ll, True)); n_gps += 1
        elif f2['區域'] in centres:
            pts.append((f2, centres[f2['區域']], False))
    if pts:
        kf = os.path.join(IN, '待定位.kml')
        with open(kf, 'w', encoding='utf-8') as fh:
            fh.write('<?xml version="1.0" encoding="UTF-8"?>\n'
                     '<kml xmlns="http://www.opengis.net/kml/2.2"><Document>'
                     '<name>新增的花（' + str(len(pts)) + ' 點）</name>'
                     '<description>標「GPS」的是照片本身的座標，通常不用調；'
                     '標「概略」的只是該區中心，要拖到實際位置。名稱不要改。</description>')
            for f2, ll, exact in pts:
                tag = 'GPS' if exact else '概略'
                fh.write(f"<Placemark><name>{f2['內部代號']} {f2['中文名']}</name>"
                         f"<description>{tag}</description>"
                         f"<Point><coordinates>{ll[1]:.7f},{ll[0]:.7f},0</coordinates></Point></Placemark>")
            fh.write('</Document></kml>')
        say(f'{kf} 可以匯入 My Maps：{n_gps} 點用照片的 GPS 座標'
            + (f'、{len(pts)-n_gps} 點只是該區中心要自己拖' if len(pts) - n_gps else ''))
    miss = [f2['中文名'] for f2 in fresh if f2['區域'] not in centres]
    if miss:
        say(f'　（{"、".join(miss)} 的區域沒有中心座標，要自己在 My Maps 加點）')

out.sort(key=lambda x: x['n'])

# 跟上次比對
SP = os.path.join(ROOT, 'src/data', SLUG + '.json')
old = {x['n']: x for x in json.load(open(SP, encoding='utf-8'))} if os.path.exists(SP) else {}
new = {x['n']: x for x in out}
gone = sorted(set(old) - set(new)); add = sorted(set(new) - set(old))
chg = [(n, old[n]['st'], new[n]['st']) for n in new if n in old and old[n]['st'] != new[n]['st']]

json.dump(out, open(SP, 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
cnt_st = collections.Counter(x['st'] for x in out)
say()
say(f'物種 {len(out)} 種　{dict(cnt_st)}　排除 {len(dropped)} 種')
if add:
    say(f'新增 {len(add)} 種：' + '、'.join(add[:30]) + ('…' if len(add) > 30 else ''))
if gone:
    say(f'移除 {len(gone)} 種：' + '、'.join(gone[:30]) + ('…' if len(gone) > 30 else ''))
if chg:
    say(f'狀態改變 {len(chg)} 種：' + '、'.join(f'{n} {a}→{b}' for n, a, b in chg[:20]))
if not (add or gone or chg):
    say('物種資料沒有變動')

# ---------- 7. 把這次用的輸入存成下次的基準 ----------
if xl_new:
    shutil.copy2(MASTER, os.path.join(DATA, '主檔.xlsx'))
if kml_new:
    kd = os.path.join(DATA, 'kml')
    shutil.rmtree(kd, ignore_errors=True); os.makedirs(kd)
    for f in kmls:
        shutil.copy2(f, kd)

# ---------- 8. 照片 ----------
CFG = os.path.join(DATA, 'config.json')
cfg = json.load(open(CFG, encoding='utf-8')) if os.path.exists(CFG) else {}
fb = None
for cand in [os.path.join(IN, 'FB匯出'), cfg.get('fb', '')]:
    if cand and os.path.isdir(os.path.join(cand, 'posts', 'album')):
        fb = cand; break
    if cand and os.path.isdir(cand):
        sub = glob.glob(os.path.join(cand, '*', 'posts', 'album'))
        if sub:
            fb = os.path.dirname(os.path.dirname(sub[0])); break
if fb:
    cfg['fb'] = fb
    json.dump(cfg, open(CFG, 'w', encoding='utf-8'), ensure_ascii=False)

say()
photo_dir = os.path.join(IN, '照片')
legacy = os.path.expanduser('~/Documents/花曆照片補充')
if not os.path.isdir(photo_dir) and os.path.isdir(legacy):
    photo_dir = legacy
if fb or os.path.isdir(photo_dir):
    say('開始處理照片…')
    t0 = time.time()
    rc = subprocess.run([sys.executable, os.path.join(ROOT, 'tools/build_photos.py'),
                         fb or '', photo_dir]).returncode
    if rc != 0:
        say('照片處理沒有完成，上面應該有錯誤訊息。')
    else:
        say(f'照片處理完成（{time.time()-t0:.0f} 秒）')
else:
    say('沒有找到 FB 匯出資料夾，也沒有補充照片，照片維持原樣。')

say()
say('全部完成。接著執行：')
say('  npm run build && git add -A && git commit -m "更新" && git push')
