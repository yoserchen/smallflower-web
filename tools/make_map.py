#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
小花老師的花曆 — 口袋地圖排版

用法（在 smallflower-web 資料夾裡執行）：
    python3 tools/make_map.py

讀 ~/Documents/花曆更新/ 裡的主檔和地圖 KML（沒有就用 tools/data 裡的基準檔），
排出四張 A3 直式、雙面的口袋地圖：正面地圖、背面索引。輸出到 ~/Documents/花曆地圖/
    口袋地圖.pdf     八頁（四張紙雙面）
    印刷編號.csv     內部代號 -> 印刷編號，確認後複製到 tools/data/ 給網站用

只收「上地圖」不是否、狀態現存、而且地圖上真的有點的花。
溫室和蘭房裡面的不畫點，地圖上框起來標號碼範圍，名字列在背面索引。
"""
import os, sys, csv, re, math, glob, collections, subprocess, zipfile, tempfile
import xml.etree.ElementTree as ET

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, 'tools/data')
IN = os.path.expanduser('~/Documents/花曆更新')
OUT = os.path.expanduser('~/Documents/花曆地圖')
SITE = 'smallflower.tw'
MAPURL = f'https://{SITE}/tpbg/map/'
NS = '{http://www.opengis.net/kml/2.2}'
ZONE_RENAME = {'蜜源植物區': '植物與昆蟲區', '名人植物區': '植物名人園區'}
VER = '草稿 v8'

# A3 直式，單位 mm
PW, PH = 297.0, 420.0
M = 13.0                       # 外邊
FOOT = 46.0                    # 下方資訊帶（含分隔線）
MAPH = PH - 2 * M - FOOT       # 地圖高度

INK = (0.114, 0.227, 0.184)
LEAF = (0.357, 0.486, 0.345)
MIST = (0.863, 0.890, 0.835)
BLOOM = (0.722, 0.200, 0.416)
PAPER = (0.973, 0.973, 0.957)
G_GARDEN = (0.871, 0.906, 0.831)
G_FOREST = (0.827, 0.875, 0.776)
G_GRASS = (0.906, 0.933, 0.875)
WATER = (0.741, 0.851, 0.902)
BUILD = (0.914, 0.898, 0.871)
WHITE = (1, 1, 1)

MM = 72 / 25.4


def say(s=''):
    print(s, flush=True)


def P(x, y):
    """mm（左上原點）-> PDF 點（左下原點）"""
    return x * MM, (PH - y) * MM


# ---------- 字型 ----------
def make_fonts(chars):
    sys.path.insert(0, os.path.join(ROOT, 'tools'))
    from otf2ttf import otf2ttf
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    tmp = tempfile.mkdtemp()
    out = {}
    text = ''.join(sorted(set(chars)))
    for fn, key in (('NotoSerifCJK-Regular.ttc', 'body'),
                    ('NotoSerifCJK-Bold.ttc', 'bold'),
                    ('NotoSansCJK-Regular.ttc', 'num')):
        p = f'/usr/share/fonts/opentype/noto/{fn}'
        otf = os.path.join(tmp, key + '.otf')
        subprocess.run([sys.executable, '-m', 'fontTools.subset', p, '--font-number=1',
                        '--text=' + text, '--output-file=' + otf,
                        '--no-hinting', '--desubroutinize'], check=True, capture_output=True)
        ttf = os.path.join(tmp, key + '.ttf')
        otf2ttf(otf, ttf)
        name = 'HL-' + key
        pdfmetrics.registerFont(TTFont(name, ttf))
        out[key] = name
    return out


# ---------- 資料 ----------
def newest(pattern, fallback):
    got = sorted(glob.glob(pattern), key=os.path.getmtime)
    return got[-1] if got else (sorted(glob.glob(fallback))[-1] if glob.glob(fallback) else None)


def load():
    from openpyxl import load_workbook
    xl = newest(os.path.join(IN, '*.xlsx'), os.path.join(DATA, '主檔.xlsx'))
    say(f'主檔：{os.path.basename(xl)}')
    ws = load_workbook(xl, data_only=True)['物種主檔']
    hd = [str(c.value).strip() if c.value else '' for c in ws[1]]
    ci = {k: i for i, k in enumerate(hd)}
    M_ = {}
    for r in ws.iter_rows(min_row=2, values_only=True):
        if not r or not r[0]:
            continue
        z = str(r[ci['區域']] or '').strip()
        mo = str(r[ci['採用月份']] or '').replace('，', ',')
        M_[str(r[0]).strip()] = dict(
            n=str(r[ci['中文名']]).strip(), z=ZONE_RENAME.get(z, z),
            up=str(r[ci['上地圖']] or '').strip(),
            st=str(r[ci['採用狀態']] or '').strip(),
            mo={int(x) for x in mo.split(',') if x.strip().isdigit()})
    pin_csv = os.path.join(DATA, '圖釘編號.csv')
    rem = list(csv.DictReader(open(pin_csv, encoding='utf-8-sig'))) \
        if os.path.exists(pin_csv) else []
    nx = 0
    for r in rem:
        if r['內部代號'] not in M_:
            M_[r['內部代號']] = dict(n=r['中文名'], z=r.get('區域') or '', up='是',
                                   st='現存', mo=set())
            nx += 1
    if nx:
        say(f'　主檔還沒有、圖釘已配號的：{nx} 個代號，一併收進來')

    kmls = sorted(glob.glob(os.path.join(IN, '地圖/*.km[lz]')), key=os.path.getmtime) \
        or sorted(glob.glob(os.path.join(DATA, 'kml/*.kml')))
    pins = collections.defaultdict(list)
    for f in kmls:
        if f.lower().endswith('.kmz'):
            z = zipfile.ZipFile(f)
            root = ET.fromstring(z.read(next(i for i in z.namelist()
                                             if i.lower().endswith('.kml'))))
        else:
            root = ET.parse(f).getroot()
        for pm in root.iter(NS + 'Placemark'):
            nm = (pm.findtext(NS + 'name') or '').strip()
            pt = pm.find('.//' + NS + 'Point')
            if pt is None:
                continue
            c = pt.find(NS + 'coordinates')
            m = re.match(r'(\S+?-\d+)', nm)
            if not m or c is None or not c.text:
                continue
            lo, la = c.text.strip().split(',')[:2]
            pins[m.group(1)].append((float(la), float(lo)))
    say(f'地圖 KML：{os.path.basename(kmls[-1])}，{sum(len(v) for v in pins.values())} 個點')
    for r in rem:
        if r['內部代號'] not in pins:
            pins[r['內部代號']].append((float(r['緯度']), float(r['經度'])))

    pts, drop = [], collections.Counter()
    for code, v in pins.items():
        m = M_.get(code)
        if not m:
            drop['地圖有、主檔沒有'] += len(v); continue
        if m['up'] == '否':
            drop['上地圖＝否'] += len(v); continue
        if m['st'] != '現存':
            drop[m['st'] or '沒有狀態'] += len(v); continue
        for la, lo in v:
            pts.append(dict(code=code, n=m['n'], z=m['z'], mo=m['mo'], la=la, lo=lo))
    say(f'要印的點：{len(pts)} 個（{len({p["code"] for p in pts})} 個代號）')
    for k, n in drop.most_common():
        say(f'　排除 {k}：{n} 個點')
    return pts


class Proj:
    def __init__(self, pts):
        la = [p['la'] for p in pts]; lo = [p['lo'] for p in pts]
        self.lo0 = min(lo); self.lam = max(la)
        self.k = math.cos(math.radians((min(la) + max(la)) / 2))

    def __call__(self, la, lo):
        return ((lo - self.lo0) * 111320 * self.k, (self.lam - la) * 111320)


# ---------- 底圖 ----------
def load_osm(prj):
    f = os.path.join(DATA, 'map.osm')
    if not os.path.exists(f):
        return [], {}
    r = ET.parse(f).getroot()
    N = {n.get('id'): (float(n.get('lat')), float(n.get('lon'))) for n in r.findall('node')}
    W = {w.get('id'): [N[x.get('ref')] for x in w.findall('nd') if x.get('ref') in N]
         for w in r.findall('way')}

    def tg(e):
        return {t.get('k'): t.get('v') for t in e.findall('tag')}

    out, special = [], {}
    trees = []
    for n in r.findall('node'):
        if tg(n).get('natural') == 'tree':
            trees.append(prj(float(n.get('lat')), float(n.get('lon'))))
    for w in r.findall('way'):
        t = tg(w); pl = [prj(a, o) for a, o in W[w.get('id')]]
        if len(pl) < 2:
            continue
        nm = t.get('name', '')
        if nm == '蘭房':
            special['蘭房'] = pl; continue
        if t.get('natural') == 'water':
            out.append(('water', pl, nm))
        elif t.get('waterway') in ('ditch', 'stream'):
            out.append(('ditch', pl, ''))
        elif t.get('landuse') == 'forest':
            out.append(('forest', pl, ''))
        elif t.get('landuse') in ('grass', 'meadow') or t.get('leisure') in ('garden', 'park'):
            out.append(('grass', pl, ''))
        elif 'building' in t:
            out.append(('build', pl, nm))
        elif t.get('highway') in ('footway', 'path', 'steps'):
            out.append(('path', pl, ''))
        elif t.get('highway') in ('pedestrian', 'service'):
            out.append(('lane', pl, ''))
        elif t.get('highway') in ('residential', 'tertiary', 'secondary', 'primary'):
            out.append(('road', pl, nm))
    for rel in r.findall('relation'):
        t = tg(rel)
        if t.get('building') == 'roof':
            seg = [W[m.get('ref')][:] for m in rel.findall('member')
                   if m.get('type') == 'way' and m.get('ref') in W
                   and m.get('role') in ('outer', '')]
            ring = []
            while seg:
                g = seg.pop(0); ch = True
                while ch and g and g[0] != g[-1]:
                    ch = False
                    for i, s in enumerate(seg):
                        if s and s[0] == g[-1]:
                            g += s[1:]; seg.pop(i); ch = True; break
                        if s and s[-1] == g[-1]:
                            g += s[::-1][1:]; seg.pop(i); ch = True; break
                if len(g) > 3:
                    ring = g if len(g) > len(ring) else ring
            if ring:
                special['溫室'] = [prj(a, o) for a, o in ring]
        elif t.get('building'):
            for m in rel.findall('member'):
                if m.get('type') == 'way' and m.get('ref') in W and m.get('role') in ('outer', ''):
                    pl = [prj(a, o) for a, o in W[m.get('ref')]]
                    if len(pl) > 2:
                        out.append(('build', pl, t.get('name', '')))
    return out, special, trees


def inside(p, poly):
    y, x = p[1], p[0]; c = False
    for i in range(len(poly)):
        x1, y1 = poly[i]; x2, y2 = poly[(i + 1) % len(poly)]
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
            c = not c
    return c


# ---------- 分張 ----------
ASPECT = (PW - 2 * M) / MAPH          # 版面寬高比


def fit(box, pad=6.0):
    """把點的範圍撐成版面比例"""
    x0, x1, y0, y1 = box
    x0 -= pad; x1 += pad; y0 -= pad; y1 += pad
    w, h = x1 - x0, y1 - y0
    if w / h < ASPECT:
        nw = h * ASPECT; cx = (x0 + x1) / 2; x0, x1 = cx - nw / 2, cx + nw / 2
    else:
        nh = w / ASPECT; cy = (y0 + y1) / 2; y0, y1 = cy - nh / 2, cy + nh / 2
    return dict(x0=x0, x1=x1, y0=y0, y1=y1)


def bbox(sel):
    return (min(p['x'] for p in sel), max(p['x'] for p in sel),
            min(p['y'] for p in sel), max(p['y'] for p in sel))


def make_sheets(pts, special):
    gh = special.get('溫室'); lf = special.get('蘭房')
    # 第 1 張：溫室 + 蘭房一帶
    anchor = (gh or []) + (lf or [])
    ax0 = min(p[0] for p in anchor); ax1 = max(p[0] for p in anchor)
    ay0 = min(p[1] for p in anchor); ay1 = max(p[1] for p in anchor)
    s1 = fit((ax0 - 10, ax1 + 10, ay0 - 10, ay1 + 10), pad=0)
    inb = lambda p, s: s['x0'] <= p['x'] <= s['x1'] and s['y0'] <= p['y'] <= s['y1']
    s1['pts'] = [p for p in pts if inb(p, s1)]
    s1['name'] = '方舟溫室'
    rest = [p for p in pts if not inb(p, s1)]

    def cut(sel, axis, frac):
        vs = sorted(p[axis] for p in sel)
        lo, hi = vs[0], vs[-1]
        want = len(sel) * frac; b = None
        for i in range(1, 200):
            c = lo + (hi - lo) * i / 200
            d = abs(sum(1 for p in sel if p[axis] < c) - want)
            if b is None or d < b[0]:
                b = (d, c)
        return b[1]

    # 其餘三張：西北 / 東側 / 南側
    yc = cut(rest, 'y', 2 / 3)
    north = [p for p in rest if p['y'] < yc]; south = [p for p in rest if p['y'] >= yc]
    xc = cut(north, 'x', 0.5)
    nw = [p for p in north if p['x'] < xc]; ne = [p for p in north if p['x'] >= xc]
    out = [s1]
    for sel, nm in ((nw, '西北'), (ne, '東側'), (south, '南側')):
        s = fit(bbox(sel)); s['pts'] = sel; s['name'] = nm
        out.append(s)
    for i, s in enumerate(out, 1):
        s['no'] = i
    return out


def number(sheet, special, band=14.0):
    """溫室內 -> 蘭房內 -> 室外，各自由北往南排；回傳分組"""
    gh = special.get('溫室'); lf = special.get('蘭房')
    grp = {'溫室內': [], '蘭房內': [], '室外': []}
    for p in sheet['pts']:
        if lf and inside((p['x'], p['y']), lf):
            grp['蘭房內'].append(p)
        elif gh and inside((p['x'], p['y']), gh):
            grp['溫室內'].append(p)
        else:
            grp['室外'].append(p)
    order = ['室外', '蘭房內', '溫室內']
    k = 0
    for g in order:
        grp[g].sort(key=lambda p: (int((p['y'] - sheet['y0']) // band), p['x']))
        for p in grp[g]:
            k += 1; p['no'] = k; p['grp'] = g
    sheet['groups'] = [(g, grp[g]) for g in order if grp[g]]
    sheet['pts'] = [p for g in order for p in grp[g]]
    sheet['outdoor'] = grp['室外']


# ---------- 放大圖 ----------
def find_insets(sheet, sc, n=2, w_m=34.0, h_m=30.0):
    """在室外的點裡找最擠的兩塊，做放大圖"""
    pts = sheet['outdoor']
    got = []
    used = []
    for _ in range(n):
        best = None
        x0, x1 = sheet['x0'], sheet['x1'] - w_m
        y0, y1 = sheet['y0'], sheet['y1'] - h_m
        for cx in [x0 + (x1 - x0) * i / 70 for i in range(71)]:
            for cy in [y0 + (y1 - y0) * j / 70 for j in range(71)]:
                if any(not (cx + w_m < u[0] or cx > u[2] or cy + h_m < u[1] or cy > u[3])
                       for u in used):
                    continue
                c = sum(1 for p in pts if cx <= p['x'] <= cx + w_m and cy <= p['y'] <= cy + h_m)
                if best is None or c > best[0]:
                    best = (c, cx, cy)
        if not best or best[0] < 28:
            break
        _, cx, cy = best
        used.append((cx, cy, cx + w_m, cy + h_m))
        got.append(dict(x0=cx, x1=cx + w_m, y0=cy, y1=cy + h_m,
                        pts=[p for p in pts if cx <= p['x'] <= cx + w_m
                             and cy <= p['y'] <= cy + h_m]))
    for i, g in enumerate(got):
        g['tag'] = '放大圖 ' + 'AB'[i]
    return got


# ---------- 標號擺放 ----------
def place(pts, T, clip, fw, fh, fsize, R=0.62):
    boxes, dots, out = [], [], []
    for p in pts:
        p['mx'], p['my'] = T(p['x'], p['y'])
        dots.append((p['mx'], p['my']))
    cand = [(1, -0.3), (-1, -0.3), (1, 0.95), (-1, 0.95), (1, -1.55), (-1, -1.55),
            (0, -1.75), (0, 1.75), (1, 2.2), (-1, 2.2)]
    fail = 0
    for p in pts:
        t = str(p['no']); w = fw(t, fsize); h = fh
        best = None
        for mult in (1.0, 1.35, 1.8, 2.5, 3.4, 4.6, 6.2, 8.5):
            for dx, dy in cand:
                gap = (R + 0.42) * mult
                x0 = p['mx'] + gap if dx > 0 else (p['mx'] - gap - w if dx < 0 else p['mx'] - w / 2)
                y0 = p['my'] + dy * gap - h / 2
                b = (x0 - .12, y0 - .12, x0 + w + .12, y0 + h + .12)
                if b[0] < clip[0] or b[2] > clip[2] or b[1] < clip[1] or b[3] > clip[3]:
                    continue
                if any(not (b[2] < q[0] or b[0] > q[2] or b[3] < q[1] or b[1] > q[3])
                       for q in boxes):
                    continue
                if any(b[0] - .25 < u < b[2] + .25 and b[1] - .25 < v < b[3] + .25
                       for u, v in dots):
                    continue
                best = (x0, y0, b, mult > 1.7)
                break
            if best:
                break
        if not best:
            fail += 1
            x0 = p['mx'] + R + 0.4; y0 = p['my'] - h / 2
            best = (x0, y0, (x0, y0, x0 + w, y0 + h), True)
        boxes.append(best[2])
        out.append((p, best[0], best[1], best[3]))
    return out, fail


# ---------- 畫底圖 ----------
def paint(c, items, special, trees, T, clip, lw_mul=1.0, labels=True, F=None):
    x0, y0, x1, y1 = clip
    c.saveState()
    pp = c.beginPath(); pp.rect(*P(x0, y1), (x1 - x0) * MM, (y1 - y0) * MM)
    c.clipPath(pp, 0, 0)
    c.setFillColorRGB(*G_GARDEN); c.rect(*P(x0, y1), (x1 - x0) * MM, (y1 - y0) * MM, 0, 1)
    c.setLineCap(1); c.setLineJoin(1)

    def poly(pl, fill=None, stroke=None, lw=0.3, close=True, dash=None):
        mm = [T(a, b) for a, b in pl]
        if max(m[0] for m in mm) < x0 - 4 or min(m[0] for m in mm) > x1 + 4:
            return
        if max(m[1] for m in mm) < y0 - 4 or min(m[1] for m in mm) > y1 + 4:
            return
        q = c.beginPath(); q.moveTo(*P(*mm[0]))
        for m in mm[1:]:
            q.lineTo(*P(*m))
        if close and fill:
            q.close()
        if fill:
            c.setFillColorRGB(*fill)
        if stroke:
            c.setStrokeColorRGB(*stroke); c.setLineWidth(lw * lw_mul * MM)
        c.setDash(dash or [])
        c.drawPath(q, 1 if stroke else 0, 1 if fill else 0)
        c.setDash([])

    for k, col in (('forest', G_FOREST), ('grass', G_GRASS)):
        for kind, pl, nm in items:
            if kind == k:
                poly(pl, fill=col)
    for kind, pl, nm in items:
        if kind == 'water':
            poly(pl, fill=WATER)
    for kind, pl, nm in items:
        if kind == 'ditch':
            poly(pl, stroke=WATER, lw=1.1, close=False)
    for x, y in trees:
        mx, my = T(x, y)
        if x0 - 2 < mx < x1 + 2 and y0 - 2 < my < y1 + 2:
            c.setFillColorRGB(0.776, 0.843, 0.722)
            c.circle(*P(mx, my), 0.55 * lw_mul * MM, 0, 1)
    for kind, pl, nm in items:
        if kind == 'build':
            poly(pl, fill=BUILD, stroke=(0.84, 0.82, 0.79), lw=0.2)
    for kind, lw in (('road', 2.6), ('lane', 1.9), ('path', 1.25)):
        for k2, pl, nm in items:
            if k2 == kind:
                poly(pl, stroke=WHITE, lw=lw, close=False)
    # 地標名稱
    if labels and F:
        c.setFont(F['body'], 5.6 * min(1.6, max(0.9, lw_mul)))
        for kind, pl, nm in items:
            if kind not in ('build', 'water') or not nm or len(nm) > 8:
                continue
            mm = [T(a, b) for a, b in pl]
            cx = sum(m[0] for m in mm) / len(mm); cy = sum(m[1] for m in mm) / len(mm)
            if not (x0 + 3 < cx < x1 - 3 and y0 + 3 < cy < y1 - 3):
                continue
            wdt = max(m[0] for m in mm) - min(m[0] for m in mm)
            hgt = max(m[1] for m in mm) - min(m[1] for m in mm)
            if wdt < 11 or hgt < 6:
                continue
            c.setFillColorRGB(*(0.33, 0.47, 0.56) if kind == 'water' else (0.50, 0.47, 0.43))
            c.drawCentredString(*P(cx, cy), nm)
    c.restoreState()


# ---------- 一張地圖 ----------
def draw_map(c, sheet, sheets, osm, special, trees, F, qr):
    from reportlab.pdfbase.pdfmetrics import stringWidth
    W = sheet['x1'] - sheet['x0']; H = sheet['y1'] - sheet['y0']
    ox, oy = M, M
    dw, dh = PW - 2 * M, MAPH
    sc = dw / W

    def T(x, y):
        return ox + (x - sheet['x0']) * sc, oy + (y - sheet['y0']) * sc

    clip = (ox, oy, ox + dw, oy + dh)
    c.setFillColorRGB(*PAPER); c.rect(0, 0, PW * MM, PH * MM, 0, 1)
    paint(c, osm, special, trees, T, clip, F=F)

    fsize = 4.3
    fw = lambda t, s: stringWidth(t, F['num'], s) * 25.4 / 72
    fh = fsize * 25.4 / 72 * 0.74

    # 溫室 / 蘭房：框起來，不畫點
    rng = {}
    for g, lst in sheet['groups']:
        if g != '室外' and lst:
            rng[g] = (min(p['no'] for p in lst), max(p['no'] for p in lst))
    for key, label in (('溫室', '溫室內'), ('蘭房', '蘭房內')):
        pl = special.get(key)
        if not pl or label not in rng:
            continue
        mm = [T(a, b) for a, b in pl]
        q = c.beginPath(); q.moveTo(*P(*mm[0]))
        for m in mm[1:]:
            q.lineTo(*P(*m))
        q.close()
        c.setFillColorRGB(0.988, 0.937, 0.953); c.setStrokeColorRGB(*BLOOM)
        c.setLineWidth(0.7 * MM); c.drawPath(q, 1, 1)
        cx = sum(m[0] for m in mm) / len(mm); cy = sum(m[1] for m in mm) / len(mm)
        a, b = rng[label]
        c.setFillColorRGB(*BLOOM); c.setFont(F['bold'], 8)
        c.drawCentredString(*P(cx, cy), key)
        c.setFont(F['num'], 7)
        c.drawCentredString(*P(cx, cy + 4), f'{a}～{b}')

    # 室外的點
    lay, fail = place(sheet['outdoor'], T, clip, fw, fh, fsize)
    insets = find_insets(sheet, sc)
    ins_pts = {id(p) for g in insets for p in g['pts']}

    c.setFont(F['num'], fsize)
    for p, lx, ly, leader in lay:
        c.setFillColorRGB(*BLOOM)
        c.circle(*P(p['mx'], p['my']), 0.62 * MM, 0, 1)
        if id(p) in ins_pts:
            continue                      # 號碼放到放大圖裡
        if leader:
            c.setStrokeColorRGB(*LEAF); c.setLineWidth(.1 * MM)
            c.line(*P(p['mx'], p['my']), *P(lx + fw(str(p['no']), fsize) / 2, ly + fh / 2))
        c.setFillColorRGB(*INK)
        c.drawString(*P(lx, ly + fh), str(p['no']))

    # 放大圖的來源框
    for g in insets:
        a = T(g['x0'], g['y0']); b = T(g['x1'], g['y1'])
        c.setStrokeColorRGB(*INK); c.setLineWidth(.35 * MM); c.setDash([2 * MM, 1.6 * MM])
        c.rect(*P(a[0], b[1]), (b[0] - a[0]) * MM, (b[1] - a[1]) * MM, 1, 0)
        c.setDash([])
        c.setFillColorRGB(*INK)
        c.rect(*P(a[0], a[1]), 15 * MM, 4 * MM, 0, 1)
        c.setFillColorRGB(1, 1, 1); c.setFont(F['body'], 5.4)
        c.drawString(*P(a[0] + 1.2, a[1] - 1.2), g['tag'])

    # 放大圖本體：放在地圖上方左右
    slots = [(ox + 4, oy + 4), (ox + dw - 4 - 92, oy + 4)]
    for i, g in enumerate(insets[:2]):
        iw, ih = 92.0, 78.0
        sx, sy = slots[i]
        isc = min(iw / (g['x1'] - g['x0']), ih / (g['y1'] - g['y0']))
        iw2, ih2 = (g['x1'] - g['x0']) * isc, (g['y1'] - g['y0']) * isc

        def TI(x, y, sx=sx, sy=sy, isc=isc, g=g):
            return sx + (x - g['x0']) * isc, sy + (y - g['y0']) * isc
        icl = (sx, sy, sx + iw2, sy + ih2)
        paint(c, osm, special, trees, TI, icl, lw_mul=isc / sc, F=F)
        il, ifail = place(g['pts'], TI, icl, fw, fh, fsize)
        c.setFont(F['num'], fsize)
        for p, lx, ly, leader in il:
            c.setFillColorRGB(*BLOOM); c.circle(*P(p['mx'], p['my']), 0.62 * MM, 0, 1)
            if leader:
                c.setStrokeColorRGB(*LEAF); c.setLineWidth(.1 * MM)
                c.line(*P(p['mx'], p['my']), *P(lx + fw(str(p['no']), fsize) / 2, ly + fh / 2))
            c.setFillColorRGB(*INK)
            c.drawString(*P(lx, ly + fh), str(p['no']))
        c.setStrokeColorRGB(*INK); c.setLineWidth(.5 * MM)
        c.rect(*P(sx, sy + ih2), iw2 * MM, ih2 * MM, 1, 0)
        c.setFillColorRGB(*INK); c.rect(*P(sx, sy), 17 * MM, 4.6 * MM, 0, 1)
        c.setFillColorRGB(1, 1, 1); c.setFont(F['body'], 6)
        c.drawString(*P(sx + 1.4, sy - 1.4), g['tag'])
        fail += ifail

    sheet['fail'] = fail

    # 比例尺、來源
    bar = 20.0 * sc
    by = oy + dh - 5
    c.setStrokeColorRGB(*INK); c.setLineWidth(.9 * MM)
    c.line(*P(ox + 5, by), *P(ox + 5 + bar, by))
    c.setFont(F['num'], 6); c.setFillColorRGB(*INK)
    c.drawString(*P(ox + 4, by + 3.6), '0')
    c.drawString(*P(ox + 5 + bar + 1.5, by + 1.2), '20 公尺')
    c.setFont(F['body'], 5); c.setFillColorRGB(0.45, 0.5, 0.44)
    c.drawRightString(*P(ox + dw - 2, by + 1.2), '底圖資料 © OpenStreetMap 貢獻者')

    # 外框
    c.setStrokeColorRGB(*MIST); c.setLineWidth(.3 * MM)
    c.rect(*P(ox, oy + dh), dw * MM, dh * MM, 1, 0)

    # ---- 下方資訊帶 ----
    ly = M + MAPH + 7                     # 分隔線
    c.setStrokeColorRGB(*MIST); c.setLineWidth(.3 * MM)
    c.line(*P(M, ly), *P(PW - M, ly))
    top = ly + 9
    # 四格位置指示（2×2，自己那一格是花色）
    g = 7.0; gap = 1.6
    for i in range(4):
        gx = M + (i % 2) * (g + gap); gy = top + (i // 2) * (g + gap)
        c.setFillColorRGB(*(BLOOM if i + 1 == sheet['no'] else MIST))
        c.rect(*P(gx, gy + g), g * MM, g * MM, 0, 1)
    tx = M + 2 * g + gap + 9
    c.setFillColorRGB(*INK); c.setFont(F['bold'], 12)
    c.drawString(*P(tx, top + 5.6), '台北植物園花曆')
    c.setFont(F['bold'], 16)
    c.drawString(*P(tx, top + 16.4), f"第 {sheet['no']} 張")
    c.drawString(*P(tx + 31, top + 16.4), sheet['name'])
    c.setFillColorRGB(*LEAF); c.setFont(F['body'], 6.4)
    dx = tx + 76
    for i, t in enumerate([
            f"{len(sheet['pts'])} 株。地圖上的數字對照背面索引，號碼由北往南排列。",
            '放大圖內的號碼請看放大圖，溫室和蘭房裡面的只標號碼範圍。',
            '背面是這一張的全部花名與開花月份。']):
        c.drawString(*P(dx, top + 4.4 + i * 5.2), t)
    if qr:
        q = 17.0
        c.drawImage(qr, *P(PW - M - q, top + q), q * MM, q * MM, mask='auto')
        c.setFont(F['body'], 5.2); c.setFillColorRGB(*LEAF)
        c.drawCentredString(*P(PW - M - q / 2, top + q + 3.6), '用編號查花')
    c.setFillColorRGB(*BLOOM); c.setFont(F['body'], 6)
    c.drawRightString(*P(PW - M - q - 6 if qr else PW - M, top + 16.4), VER)
    c.showPage()


# ---------- 索引頁 ----------
def draw_index(c, sheet, F):
    from reportlab.pdfbase.pdfmetrics import stringWidth
    c.setFillColorRGB(*PAPER); c.rect(0, 0, PW * MM, PH * MM, 0, 1)
    c.setFillColorRGB(*INK); c.setFont(F['bold'], 12)
    c.drawString(*P(M, M + 6), f"第 {sheet['no']} 張　{sheet['name']}　花名索引")
    c.setFillColorRGB(*LEAF); c.setFont(F['body'], 6.5)
    c.drawString(*P(M, M + 11.5), '右邊的小格是開花月份，由左到右一月到十二月。')
    c.drawRightString(*P(PW - M, M + 11.5), f'{MAPURL}')
    c.setStrokeColorRGB(*MIST); c.setLineWidth(.3 * MM)
    c.line(*P(M, M + 14), *P(PW - M, M + 14))

    top = M + 19
    bot = PH - M
    COLS = 4
    cw = (PW - 2 * M) / COLS
    rows = []
    for g, lst in sheet['groups']:
        if len(sheet['groups']) > 1:
            rows.append(('H', g, min(p['no'] for p in lst), max(p['no'] for p in lst)))
        for p in lst:
            rows.append(('R', p))
    per = math.ceil(len(rows) / COLS)
    lh = (bot - top) / per
    lh = max(2.9, min(lh, 4.2))
    fs = min(6.2, lh * 1.55)
    for i, row in enumerate(rows):
        col = i // per; y = top + (i % per) * lh
        x = M + col * cw
        if row[0] == 'H':
            c.setFillColorRGB(*BLOOM); c.setFont(F['bold'], fs * .95)
            c.drawString(*P(x, y + lh * .72), f'{row[1]}（{row[2]}～{row[3]}）')
            c.setStrokeColorRGB(*BLOOM); c.setLineWidth(.25 * MM)
            c.line(*P(x, y + lh * .9), *P(x + cw - 6, y + lh * .9))
            continue
        p = row[1]
        c.setFillColorRGB(*LEAF); c.setFont(F['num'], fs * .9)
        c.drawRightString(*P(x + 7, y + lh * .72), str(p['no']))
        c.setFillColorRGB(*INK); c.setFont(F['body'], fs)
        nm = p['n']
        while stringWidth(nm, F['body'], fs) * 25.4 / 72 > cw - 28 and len(nm) > 2:
            nm = nm[:-1]
        c.drawString(*P(x + 9, y + lh * .72), nm)
        bw = 1.15; bx = x + cw - 6 - 12 * bw
        for mth in range(1, 13):
            c.setFillColorRGB(*(LEAF if mth in p['mo'] else (0.90, 0.92, 0.88)))
            c.rect(*P(bx + (mth - 1) * bw, y + lh * .72), bw * .78 * MM, lh * .5 * MM, 0, 1)
    c.showPage()


def main():
    os.makedirs(OUT, exist_ok=True)
    pts = load()
    prj = Proj(pts)
    osm, special, trees = load_osm(prj)
    say(f'底圖：{len(osm)} 個圖徵、{len(trees)} 棵樹、'
        + '、'.join(k for k in special) + ' 有輪廓')
    for p in pts:
        p['x'], p['y'] = prj(p['la'], p['lo'])
    sheets = make_sheets(pts, special)
    for s in sheets:
        number(s, special)
        say(f"第 {s['no']} 張　{s['name']}　{len(s['pts'])} 株　"
            + '、'.join(f'{g} {len(l)}' for g, l in s['groups']))

    chars = set('0123456789～()（）、。，；：「」【】·.:/ -　' + SITE + MAPURL + VER
                + '台北植物園花曆第張株地圖上的數字對照背面索引號碼由北往南排列放大內請看溫室和蘭房裡只標範圍'
                + '全部花名與開花月份右邊小格是左到一二三四五六七八九十公尺用編號查底資料貢獻者草稿'
                + ''.join(p['n'] for p in pts) + ''.join(s['name'] for s in sheets)
                + ''.join(nm for _, _, nm in osm if nm))
    chars |= set('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ©')
    F = make_fonts(chars)

    qr = os.path.join(OUT, 'qr.png')
    try:
        import qrcode
        qrcode.make(MAPURL).save(qr)
    except Exception as e:
        say(f'  ! 做不出 QR code：{e}'); qr = None

    from reportlab.pdfgen import canvas
    pdf = os.path.join(OUT, '口袋地圖.pdf')
    c = canvas.Canvas(pdf, pagesize=(PW * MM, PH * MM))
    c.setTitle('台北植物園花曆口袋地圖')
    for s in sheets:
        draw_map(c, s, sheets, osm, special, trees, F, qr)
        draw_index(c, s, F)
    c.save()
    bad = sum(s.get('fail', 0) for s in sheets)
    for s in sheets:
        if s.get('fail'):
            say(f"　第 {s['no']} 張有 {s['fail']} 個號碼擠不開")
    say(f'\n{pdf}　八頁（四張 A3 雙面）'
        + ('' if not bad else f'　{bad} 個號碼還擠在一起'))

    pn = collections.defaultdict(list)
    for s in sheets:
        for p in s['pts']:
            pn[p['code']].append(f"{s['no']}-{p['no']}")
    f2 = os.path.join(OUT, '印刷編號.csv')
    with open(f2, 'w', encoding='utf-8-sig', newline='') as fh:
        w = csv.writer(fh); w.writerow(['內部代號', '印刷編號', '說明'])
        for code in sorted(pn):
            w.writerow([code, '、'.join(sorted(pn[code], key=lambda t: (
                int(t.split('-')[0]), int(t.split('-')[1])))), ''])
    say(f'{f2}　{len(pn)} 個代號')


if __name__ == '__main__':
    main()
