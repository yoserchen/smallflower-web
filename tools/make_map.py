#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
小花老師的花曆 — 口袋地圖排版（接續 v7）

用法（在 smallflower-web 資料夾裡執行）：
    python3 tools/make_map.py

重點：**編號沿用 tools/data/印刷編號.csv**，也就是網站上現在用的那一套。
已經有編號的花維持原號不動，只有新加的花才在該張的最後接新號，
已經不印的花把號碼退掉（留空號，不補位），這樣紙本和網站永遠對得上。

底圖用 My Maps 裡的「OSM參考底圖」圖層（步道、建築、水池、溫室），
綠地用 tools/data/map.osm 補。

輸出到 ~/Documents/花曆地圖/
    口袋地圖.pdf     八頁（四張 A3 直式雙面）：正面地圖、背面索引
    印刷編號.csv     更新後的對照表，確認後複製到 tools/data/ 再跑 update.py
    編號異動.csv     這一版退掉和新增了哪些號碼
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
VER = 'v8'
SHEET_NAME = {1: '方舟溫室', 2: '西北', 3: '東側', 4: '南側'}

PW, PH = 297.0, 420.0          # A3 直式
M = 12.0
FOOT = 42.0
MAPH = PH - 2 * M - FOOT
MM = 72 / 25.4

INK = (0.114, 0.227, 0.184)
LEAF = (0.357, 0.486, 0.345)
MIST = (0.863, 0.890, 0.835)
BLOOM = (0.722, 0.200, 0.416)
PAPER = (0.973, 0.973, 0.957)
FIELD = (0.878, 0.910, 0.843)      # 園區綠底
FOREST = (0.835, 0.878, 0.784)
GRASS = (0.914, 0.937, 0.882)
WATER = (0.416, 0.690, 0.902)      # 6AB0E6
BUILDC = (0.863, 0.784, 0.706)     # DCC8B4
PATH = (1, 1, 1)


def say(s=''):
    print(s, flush=True)


def P(x, y):
    return x * MM, (PH - y) * MM


def make_fonts(chars):
    sys.path.insert(0, os.path.join(ROOT, 'tools'))
    from otf2ttf import otf2ttf
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    tmp = tempfile.mkdtemp(); out = {}
    text = ''.join(sorted(set(chars)))
    for fn, key in (('NotoSerifCJK-Regular.ttc', 'body'),
                    ('NotoSerifCJK-Bold.ttc', 'bold'),
                    ('NotoSansCJK-Regular.ttc', 'num'),
                    ('NotoSansCJK-Bold.ttc', 'numb')):
        otf = os.path.join(tmp, key + '.otf')
        subprocess.run([sys.executable, '-m', 'fontTools.subset',
                        f'/usr/share/fonts/opentype/noto/{fn}', '--font-number=1',
                        '--text=' + text, '--output-file=' + otf,
                        '--no-hinting', '--desubroutinize'], check=True, capture_output=True)
        ttf = os.path.join(tmp, key + '.ttf'); otf2ttf(otf, ttf)
        pdfmetrics.registerFont(TTFont('HL-' + key, ttf)); out[key] = 'HL-' + key
    return out


def newest(pattern, fallback):
    got = sorted(glob.glob(pattern), key=os.path.getmtime)
    return got[-1] if got else (sorted(glob.glob(fallback))[-1] if glob.glob(fallback) else None)


def kml_root(f):
    if f.lower().endswith('.kmz'):
        z = zipfile.ZipFile(f)
        return ET.fromstring(z.read(next(i for i in z.namelist() if i.lower().endswith('.kml'))))
    return ET.parse(f).getroot()


# ---------- 讀資料 ----------
def load():
    from openpyxl import load_workbook
    xl = newest(os.path.join(IN, '*.xlsx'), os.path.join(DATA, '主檔.xlsx'))
    say(f'主檔：{os.path.basename(xl)}')
    ws = load_workbook(xl, data_only=True)['物種主檔']
    hd = [str(c.value).strip() if c.value else '' for c in ws[1]]
    ci = {k: i for i, k in enumerate(hd)}
    sp = {}
    for r in ws.iter_rows(min_row=2, values_only=True):
        if not r or not r[0]:
            continue
        mo = str(r[ci['採用月份']] or '').replace('，', ',')
        sp[str(r[0]).strip()] = dict(
            n=str(r[ci['中文名']]).strip(), up=str(r[ci['上地圖']] or '').strip(),
            st=str(r[ci['採用狀態']] or '').strip(),
            mo={int(x) for x in mo.split(',') if x.strip().isdigit()})
    rem = list(csv.DictReader(open(os.path.join(DATA, '圖釘編號.csv'), encoding='utf-8-sig'))) \
        if os.path.exists(os.path.join(DATA, '圖釘編號.csv')) else []
    nx = 0
    for r in rem:
        if r['內部代號'] not in sp:
            sp[r['內部代號']] = dict(n=r['中文名'], up='是', st='現存', mo=set()); nx += 1
    if nx:
        say(f'　主檔還沒有、圖釘已配號的：{nx} 個代號')

    kf = newest(os.path.join(IN, '地圖/*.km[lz]'), os.path.join(DATA, 'kml/*.kml'))
    say(f'地圖：{os.path.basename(kf)}')
    root = kml_root(kf)
    pins = collections.defaultdict(list)
    for pm in root.iter(NS + 'Placemark'):
        nm = (pm.findtext(NS + 'name') or '').strip()
        pt = pm.find('.//' + NS + 'Point')
        if pt is None:
            continue
        c = pt.find(NS + 'coordinates'); m = re.match(r'(\S+?-\d+)', nm)
        if not m or c is None or not c.text:
            continue
        lo, la = c.text.strip().split(',')[:2]
        pins[m.group(1)].append((float(la), float(lo)))
    for r in rem:
        if r['內部代號'] not in pins:
            pins[r['內部代號']].append((float(r['緯度']), float(r['經度'])))

    pts, drop = [], collections.Counter()
    for code, v in pins.items():
        s = sp.get(code)
        if not s:
            drop['地圖有、主檔沒有'] += len(v); continue
        if s['up'] == '否':
            drop['上地圖＝否'] += len(v); continue
        if s['st'] != '現存':
            drop[s['st'] or '沒有狀態'] += len(v); continue
        for la, lo in v:
            pts.append(dict(code=code, n=s['n'], mo=s['mo'], la=la, lo=lo))
    say(f'要印的點：{len(pts)} 個（{len({p["code"] for p in pts})} 個代號）')
    for k, n in drop.most_common():
        say(f'　排除 {k}：{n} 個點')
    return pts, root


class Proj:
    def __init__(self, pts):
        la = [p['la'] for p in pts]; lo = [p['lo'] for p in pts]
        self.lo0 = min(lo); self.lam = max(la)
        self.k = math.cos(math.radians((min(la) + max(la)) / 2))

    def __call__(self, la, lo):
        return ((lo - self.lo0) * 111320 * self.k, (self.lam - la) * 111320)


# ---------- 底圖 ----------
def base_from_kml(root, prj):
    """My Maps 的「OSM參考底圖」「區域邊界」圖層"""
    doc = root.find(NS + 'Document') or root
    out = {'path': [], 'lane': [], 'road': [], 'build': [], 'water': [],
           'glass': [], 'zone': [], 'label': []}
    for fo in doc.findall(NS + 'Folder'):
        lay = (fo.findtext(NS + 'name') or '').strip()
        if lay not in ('OSM參考底圖', '區域邊界'):
            continue
        for pm in fo.findall(NS + 'Placemark'):
            nm = (pm.findtext(NS + 'name') or '').strip()
            su = (pm.findtext(NS + 'styleUrl') or '')
            rings = []
            for co in pm.iter(NS + 'coordinates'):
                pl = []
                for t in co.text.split():
                    a = t.split(',')
                    if len(a) >= 2:
                        pl.append(prj(float(a[1]), float(a[0])))
                if len(pl) > 1:
                    rings.append(pl)
            if not rings:
                continue
            poly = pm.find('.//' + NS + 'Polygon') is not None
            if lay == '區域邊界':
                out['zone'] += [(r, nm) for r in rings]; continue
            if '6AB0E6' in su:
                out['water'] += [(r, nm) for r in rings]
            elif 'FFFFFF' in su and poly:
                out['glass'] += [(r, nm) for r in rings]
            elif 'DCC8B4' in su:
                out['build'] += [(r, nm) for r in rings]
            elif '999999' in su:
                out['road'] += [(r, nm) for r in rings]
            elif '777777' in su:
                out['lane'] += [(r, nm) for r in rings]
            elif '555555' in su:
                out['path'] += [(r, nm) for r in rings]
    return out


def green_from_osm(prj):
    f = os.path.join(DATA, 'map.osm')
    if not os.path.exists(f):
        return []
    r = ET.parse(f).getroot()
    N = {n.get('id'): (float(n.get('lat')), float(n.get('lon'))) for n in r.findall('node')}
    W = {w.get('id'): [N[x.get('ref')] for x in w.findall('nd') if x.get('ref') in N]
         for w in r.findall('way')}

    def tg(e):
        return {t.get('k'): t.get('v') for t in e.findall('tag')}
    out = []
    for w in r.findall('way'):
        t = tg(w); pl = [prj(a, o) for a, o in W[w.get('id')]]
        if len(pl) < 3:
            continue
        if t.get('landuse') == 'forest':
            out.append((FOREST, pl))
        elif t.get('landuse') in ('grass', 'meadow') or t.get('leisure') in ('garden', 'park'):
            out.append((GRASS, pl))
    lan = [[prj(a, o) for a, o in W[w.get('id')]] for w in r.findall('way')
           if tg(w).get('name') == '蘭房']
    ark = None
    for rel in r.findall('relation'):
        if tg(rel).get('building') != 'roof':
            continue
        seg = [W[m.get('ref')][:] for m in rel.findall('member')
               if m.get('type') == 'way' and m.get('ref') in W and m.get('role') in ('outer', '')]
        ring = []
        while seg:
            g = seg.pop(0); ch = True
            while ch and g and g[0] != g[-1]:
                ch = False
                for i, sg in enumerate(seg):
                    if sg and sg[0] == g[-1]:
                        g += sg[1:]; seg.pop(i); ch = True; break
                    if sg and sg[-1] == g[-1]:
                        g += sg[::-1][1:]; seg.pop(i); ch = True; break
            if len(g) > len(ring):
                ring = g
        if len(ring) > 3:
            ark = [prj(a, o) for a, o in ring]
    return out, (lan[0] if lan else None), ark


def inside(pt, poly):
    x, y = pt; c = False
    for i in range(len(poly)):
        x1, y1 = poly[i]; x2, y2 = poly[(i + 1) % len(poly)]
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
            c = not c
    return c


# ---------- 編號：沿用 v7 ----------
def trimmed_box(sel, q=0.012):
    xs = sorted(p['x'] for p in sel); ys = sorted(p['y'] for p in sel)
    i = max(1, int(len(xs) * q))
    return (xs[i - 1], xs[-i], ys[i - 1], ys[-i])


def assign(pts, prj):
    old = {}
    for r in csv.DictReader(open(os.path.join(DATA, '印刷編號.csv'), encoding='utf-8-sig')):
        if r['印刷編號']:
            old[r['內部代號']] = [t.strip() for t in r['印刷編號'].split('、') if t.strip()]
    for p in pts:
        p['x'], p['y'] = prj(p['la'], p['lo'])
    by = collections.defaultdict(list)
    for p in pts:
        by[p['code']].append(p)
    used = collections.defaultdict(set)

    # 第一輪：號碼數＝點數，而且全部在同一張 -> 由北到南直接對上
    for code, g in by.items():
        nums = old.get(code, [])
        if not nums or len(nums) != len(g):
            continue
        sh = {int(n.split('-')[0]) for n in nums}
        if len(sh) != 1:
            continue
        s = sh.pop()
        for p, n in zip(sorted(g, key=lambda q: (q['y'], q['x'])),
                        sorted(nums, key=lambda n: int(n.split('-')[1]))):
            p['sheet'] = s; p['no'] = int(n.split('-')[1]); used[s].add(p['no'])

    # 用這些點畫出四張的範圍（去掉極端值）
    rect = {}
    for s in (1, 2, 3, 4):
        sel = [p for p in pts if p.get('sheet') == s]
        rect[s] = trimmed_box(sel)
        say(f'　第 {s} 張的 v7 範圍：{rect[s][1]-rect[s][0]:.0f}×{rect[s][3]-rect[s][2]:.0f} m'
            f'（{len(sel)} 個點定位）')

    def dist(p, s):
        x0, x1, y0, y1 = rect[s]
        dx = max(x0 - p['x'], 0, p['x'] - x1); dy = max(y0 - p['y'], 0, p['y'] - y1)
        return math.hypot(dx, dy)

    def which(p, allow=None):
        return min(allow or (1, 2, 3, 4), key=lambda s: dist(p, s))

    # 第二輪：剩下有舊號的，依位置落在哪一張就拿那一張的號
    for code, g in by.items():
        nums = [n for n in old.get(code, [])
                if int(n.split('-')[1]) not in used[int(n.split('-')[0])]]
        todo = [p for p in g if 'sheet' not in p]
        if not nums or not todo:
            continue
        for p in sorted(todo, key=lambda q: (q['y'], q['x'])):
            if not nums:
                break
            s = which(p, {int(n.split('-')[0]) for n in nums})
            if dist(p, s) > 25:        # 這個點不在那一張的範圍內，不要硬塞舊號
                continue
            pick = sorted((n for n in nums if int(n.split('-')[0]) == s),
                          key=lambda n: int(n.split('-')[1]))[0]
            nums.remove(pick)
            p['sheet'] = s; p['no'] = int(pick.split('-')[1]); used[s].add(p['no'])

    # 第三輪：全新的點，落在哪一張就在那一張最後接號
    nxt = {s: max(used[s]) + 1 for s in used}
    fresh = sorted((p for p in pts if 'sheet' not in p), key=lambda q: (q['y'], q['x']))
    for p in fresh:
        s = which(p)
        p['sheet'] = s; p['no'] = nxt[s]; nxt[s] += 1; used[s].add(p['no'])
    have = {(p['sheet'], p['no']) for p in pts}
    gone = [(n, code) for code, nums in old.items() for n in nums
            if (int(n.split('-')[0]), int(n.split('-')[1])) not in have]
    say(f'沿用 v7 的號碼 {len(pts) - len(fresh)} 個，新號 {len(fresh)} 個，退掉 {len(gone)} 個')
    return fresh, gone, rect


# ---------- 標號擺放 ----------
def place(pts, T, clip, fw, fh, fs, R=0.62):
    boxes, dots, out = [], [], []
    for p in pts:
        p['mx'], p['my'] = T(p['x'], p['y'])
        dots.append((p['mx'], p['my']))
    cand = [(1, -0.3), (-1, -0.3), (1, 0.95), (-1, 0.95), (1, -1.55), (-1, -1.55),
            (0, -1.7), (0, 1.7), (1, 2.2), (-1, 2.2)]
    fail = 0
    for p in pts:
        t = str(p['no']); w = fw(t, fs)
        best = None
        for mu in (1.0, 1.35, 1.8, 2.5, 3.4, 4.6, 6.2, 8.5, 11.5):
            for dx, dy in cand:
                gap = (R + 0.4) * mu
                x0 = p['mx'] + gap if dx > 0 else (p['mx'] - gap - w if dx < 0 else p['mx'] - w / 2)
                y0 = p['my'] + dy * gap - fh / 2
                b = (x0 - .1, y0 - .1, x0 + w + .1, y0 + fh + .1)
                if b[0] < clip[0] or b[2] > clip[2] or b[1] < clip[1] or b[3] > clip[3]:
                    continue
                if any(not (b[2] < q[0] or b[0] > q[2] or b[3] < q[1] or b[1] > q[3])
                       for q in boxes):
                    continue
                if any(b[0] - .22 < u < b[2] + .22 and b[1] - .22 < v < b[3] + .22
                       for u, v in dots):
                    continue
                best = (x0, y0, b, mu > 1.7); break
            if best:
                break
        if not best:
            fail += 1
            x0 = p['mx'] + R + 0.4; y0 = p['my'] - fh / 2
            best = (x0, y0, (x0, y0, x0 + w, y0 + fh), True)
        boxes.append(best[2]); out.append((p, best[0], best[1], best[3]))
    return out, fail


# ---------- 畫底圖 ----------
def paint(c, base, greens, T, clip, k=1.0, F=None, labels=True):
    x0, y0, x1, y1 = clip
    c.saveState()
    q = c.beginPath(); q.rect(*P(x0, y1), (x1 - x0) * MM, (y1 - y0) * MM)
    c.clipPath(q, 0, 0)
    c.setFillColorRGB(*FIELD); c.rect(*P(x0, y1), (x1 - x0) * MM, (y1 - y0) * MM, 0, 1)
    c.setLineCap(1); c.setLineJoin(1)

    def draw(pl, fill=None, stroke=None, lw=0.3, close=True):
        mm = [T(a, b) for a, b in pl]
        if max(m[0] for m in mm) < x0 - 4 or min(m[0] for m in mm) > x1 + 4 \
           or max(m[1] for m in mm) < y0 - 4 or min(m[1] for m in mm) > y1 + 4:
            return
        pp = c.beginPath(); pp.moveTo(*P(*mm[0]))
        for m in mm[1:]:
            pp.lineTo(*P(*m))
        if close and fill:
            pp.close()
        if fill:
            c.setFillColorRGB(*fill)
        if stroke:
            c.setStrokeColorRGB(*stroke); c.setLineWidth(lw * k * MM)
        c.drawPath(pp, 1 if stroke else 0, 1 if fill else 0)

    for col, pl in greens:
        draw(pl, fill=col)
    for pl, nm in base['zone']:
        draw(pl, fill=(0.847, 0.894, 0.800))
    for pl, nm in base['water']:
        draw(pl, fill=WATER)
    for pl, nm in base['build']:
        draw(pl, fill=BUILDC, stroke=(0.80, 0.72, 0.64), lw=0.18)
    for key, lw in (('road', 3.2), ('lane', 2.3), ('path', 1.35)):
        for pl, nm in base[key]:
            draw(pl, stroke=PATH, lw=lw, close=False)
    for pl, nm in base['glass']:
        draw(pl, fill=(1, 1, 1), stroke=(0.72, 0.72, 0.70), lw=0.25)
    if labels and F:
        c.setFont(F['body'], 5.4 * min(1.7, max(0.95, k)))
        seen = set()
        for key, col in (('build', (0.47, 0.41, 0.35)), ('water', (0.18, 0.40, 0.56))):
            for pl, nm in base[key]:
                if not nm or nm in ('建築', '水池', '溫室') or nm in seen or len(nm) > 9:
                    continue
                mm = [T(a, b) for a, b in pl]
                cx = sum(m[0] for m in mm) / len(mm); cy = sum(m[1] for m in mm) / len(mm)
                if not (x0 + 4 < cx < x1 - 4 and y0 + 4 < cy < y1 - 4):
                    continue
                if max(m[0] for m in mm) - min(m[0] for m in mm) < 10:
                    continue
                seen.add(nm); c.setFillColorRGB(*col)
                c.drawCentredString(*P(cx, cy), nm)
    c.restoreState()


def find_insets(sheet, n=2, w_m=36.0, h_m=31.0):
    pts = sheet['out']; got = []; used = []
    for _ in range(n):
        best = None
        for cx in [sheet['x0'] + (sheet['x1'] - sheet['x0'] - w_m) * i / 60 for i in range(61)]:
            for cy in [sheet['y0'] + (sheet['y1'] - sheet['y0'] - h_m) * j / 60 for j in range(61)]:
                if any(not (cx + w_m < u[0] or cx > u[2] or cy + h_m < u[1] or cy > u[3])
                       for u in used):
                    continue
                t = sum(1 for p in pts if cx <= p['x'] <= cx + w_m and cy <= p['y'] <= cy + h_m)
                if best is None or t > best[0]:
                    best = (t, cx, cy)
        if not best or best[0] < 30:
            break
        _, cx, cy = best
        used.append((cx, cy, cx + w_m, cy + h_m))
        got.append(dict(x0=cx, x1=cx + w_m, y0=cy, y1=cy + h_m,
                        pts=[p for p in pts if cx <= p['x'] <= cx + w_m
                             and cy <= p['y'] <= cy + h_m]))
    for i, g in enumerate(got):
        g['tag'] = '放大圖 ' + 'AB'[i]
    return got


# ---------- 一張地圖 ----------
def draw_map(c, sheet, base, greens, F, qr):
    from reportlab.pdfbase.pdfmetrics import stringWidth
    ox, oy = M, M
    dw, dh = PW - 2 * M, MAPH
    sc = dw / (sheet['x1'] - sheet['x0'])

    def T(x, y):
        return ox + (x - sheet['x0']) * sc, oy + (y - sheet['y0']) * sc
    clip = (ox, oy, ox + dw, oy + dh)
    c.setFillColorRGB(*PAPER); c.rect(0, 0, PW * MM, PH * MM, 0, 1)
    paint(c, base, greens, T, clip, F=F)

    fs = 4.4
    fw = lambda t, s: stringWidth(t, F['numb'], s) * 25.4 / 72
    fh = fs * 25.4 / 72 * 0.74

    for key, pls in (('溫室', sheet.get('glass_pl') or []), ('蘭房', sheet.get('lan_pl') or [])):
        rg = sheet['rng'].get(key)
        if not rg or not pls:
            continue
        allp = [q for pl in pls for q in pl]
        mm = [T(a, b) for a, b in allp]
        cx = (min(m[0] for m in mm) + max(m[0] for m in mm)) / 2
        cy = (min(m[1] for m in mm) + max(m[1] for m in mm)) / 2
        for pl in pls:
            mm2 = [T(a, b) for a, b in pl]
            pp = c.beginPath(); pp.moveTo(*P(*mm2[0]))
            for m in mm2[1:]:
                pp.lineTo(*P(*m))
            pp.close()
            c.setFillColorRGB(0.992, 0.949, 0.961); c.setStrokeColorRGB(*BLOOM)
            c.setLineWidth(0.6 * MM); c.drawPath(pp, 1, 1)
        c.setFillColorRGB(*BLOOM); c.setFont(F['bold'], 8.5)
        c.drawCentredString(*P(cx, cy), key)
        c.setFont(F['numb'], 7.5)
        c.drawCentredString(*P(cx, cy + 4.4), f'{rg[0]}～{rg[1]}')

    lay, fail = place(sheet['out'], T, clip, fw, fh, fs)
    insets = find_insets(sheet)
    skip = {id(p) for g in insets for p in g['pts']}
    c.setFont(F['numb'], fs)
    for p, lx, ly, leader in lay:
        c.setFillColorRGB(*BLOOM); c.circle(*P(p['mx'], p['my']), 0.6 * MM, 0, 1)
        if id(p) in skip:
            continue
        if leader:
            c.setStrokeColorRGB(0.72, 0.60, 0.66); c.setLineWidth(.1 * MM)
            c.line(*P(p['mx'], p['my']), *P(lx + fw(str(p['no']), fs) / 2, ly + fh / 2))
        c.setFillColorRGB(*BLOOM)
        c.drawString(*P(lx, ly + fh), str(p['no']))

    for g in insets:
        a = T(g['x0'], g['y0']); b = T(g['x1'], g['y1'])
        c.setStrokeColorRGB(*INK); c.setLineWidth(.35 * MM); c.setDash([2 * MM, 1.6 * MM])
        c.rect(*P(a[0], b[1]), (b[0] - a[0]) * MM, (b[1] - a[1]) * MM, 1, 0); c.setDash([])
        c.setFillColorRGB(*INK); c.rect(*P(a[0], a[1]), 15 * MM, 4.2 * MM, 0, 1)
        c.setFillColorRGB(1, 1, 1); c.setFont(F['body'], 5.4)
        c.drawString(*P(a[0] + 1.2, a[1] - 1.1), g['tag'])

    iw, ih = 108.0, 84.0
    slots = [(ox + 3, oy + 3), (ox + dw - 3 - iw, oy + 3)]
    for i, g in enumerate(insets[:2]):
        sx, sy = slots[i]
        isc = min(iw / (g['x1'] - g['x0']), ih / (g['y1'] - g['y0']))
        w2, h2 = (g['x1'] - g['x0']) * isc, (g['y1'] - g['y0']) * isc
        if i == 1:
            sx = ox + dw - 3 - w2

        def TI(x, y, sx=sx, sy=sy, isc=isc, g=g):
            return sx + (x - g['x0']) * isc, sy + (y - g['y0']) * isc
        icl = (sx, sy, sx + w2, sy + h2)
        paint(c, base, greens, TI, icl, k=isc / sc, F=F, labels=False)
        il, f2 = place(g['pts'], TI, icl, fw, fh, fs)
        c.setFont(F['numb'], fs)
        for p, lx, ly, leader in il:
            c.setFillColorRGB(*BLOOM); c.circle(*P(p['mx'], p['my']), 0.6 * MM, 0, 1)
            if leader:
                c.setStrokeColorRGB(0.72, 0.60, 0.66); c.setLineWidth(.1 * MM)
                c.line(*P(p['mx'], p['my']), *P(lx + fw(str(p['no']), fs) / 2, ly + fh / 2))
            c.setFillColorRGB(*BLOOM); c.drawString(*P(lx, ly + fh), str(p['no']))
        c.setStrokeColorRGB(*INK); c.setLineWidth(.5 * MM)
        c.rect(*P(sx, sy + h2), w2 * MM, h2 * MM, 1, 0)
        c.setFillColorRGB(*INK); c.rect(*P(sx, sy), 17 * MM, 4.6 * MM, 0, 1)
        c.setFillColorRGB(1, 1, 1); c.setFont(F['body'], 6)
        c.drawString(*P(sx + 1.4, sy - 1.3), g['tag'])
        fail += f2
    sheet['fail'] = fail

    bar = 20.0 * sc; by = oy + dh - 5
    c.setStrokeColorRGB(*INK); c.setLineWidth(.9 * MM)
    c.line(*P(ox + 5, by), *P(ox + 5 + bar, by))
    c.setFont(F['num'], 6); c.setFillColorRGB(*INK)
    c.drawString(*P(ox + 3.6, by + 3.4), '0')
    c.drawString(*P(ox + 5 + bar + 1.5, by + 1.2), '20 公尺')
    c.setFont(F['body'], 5); c.setFillColorRGB(0.45, 0.5, 0.44)
    c.drawRightString(*P(ox + dw - 2, by + 1.2), '底圖資料 © OpenStreetMap 貢獻者')
    c.setStrokeColorRGB(*MIST); c.setLineWidth(.3 * MM)
    c.rect(*P(ox, oy + dh), dw * MM, dh * MM, 1, 0)

    # 資訊帶
    ly2 = M + MAPH + 6
    c.setStrokeColorRGB(*MIST); c.setLineWidth(.3 * MM)
    c.line(*P(M, ly2), *P(PW - M, ly2))
    top = ly2 + 8
    c.drawImage(os.path.join(OUT, 'logo.png'), *P(M, top + 17), 17 * MM, 17 * MM, mask='auto') \
        if os.path.exists(os.path.join(OUT, 'logo.png')) else None
    tx = M + 21
    c.setFillColorRGB(*INK); c.setFont(F['bold'], 12)
    c.drawString(*P(tx, top + 5.4), '台北植物園花曆')
    c.setFont(F['bold'], 16)
    c.drawString(*P(tx, top + 16), f"第 {sheet['no']} 張")
    c.drawString(*P(tx + 31, top + 16), sheet['name'])
    c.setFillColorRGB(*LEAF); c.setFont(F['body'], 6.4)
    dx = tx + 76
    for i, t in enumerate([
            f"{sheet['n_all']} 株。地圖上的數字對照背面索引，號碼由北往南排列。",
            '放大圖內的號碼請看放大圖，溫室和蘭房裡面的只標號碼範圍。',
            '背面是這一張的全部花名與開花月份，對折四摺可放進口袋。']):
        c.drawString(*P(dx, top + 4.2 + i * 5.2), t)
    q = 16.0
    if qr:
        c.drawImage(qr, *P(PW - M - q, top + q), q * MM, q * MM, mask='auto')
        c.setFont(F['body'], 5.2); c.setFillColorRGB(*LEAF)
        c.drawCentredString(*P(PW - M - q / 2, top + q + 3.6), '用編號查花')
    c.setFillColorRGB(*BLOOM); c.setFont(F['body'], 6)
    c.drawRightString(*P(PW - M - q - 6, top + 16), VER)
    c.showPage()


# ---------- 索引（四欄＝四摺）----------
def draw_index(c, sheet, F):
    from reportlab.pdfbase.pdfmetrics import stringWidth
    c.setFillColorRGB(*PAPER); c.rect(0, 0, PW * MM, PH * MM, 0, 1)
    COLS = 4
    cw = PW / COLS
    # 摺線
    c.setStrokeColorRGB(*MIST); c.setLineWidth(.2 * MM); c.setDash([1 * MM, 2 * MM])
    for i in range(1, COLS):
        c.line(*P(cw * i, 4), *P(cw * i, PH - 4))
    c.setDash([])
    top = M + 14; bot = PH - M
    rows = []
    for g, lst in sheet['groups']:
        if len(sheet['groups']) > 1:
            rows.append(('H', g, min(p['no'] for p in lst), max(p['no'] for p in lst)))
        rows += [('R', p) for p in lst]
    per = math.ceil(len(rows) / COLS)
    lh = min(3.9, (bot - top) / max(per, 1))
    fs = min(6.0, lh * 1.55)
    for col in range(COLS):
        x = cw * col + 6
        c.setFillColorRGB(*INK); c.setFont(F['bold'], 8.5)
        c.drawString(*P(x, M + 4), f"第 {sheet['no']} 張　{sheet['name']}")
        c.setFillColorRGB(*LEAF); c.setFont(F['body'], 5.2)
        c.drawString(*P(x, M + 8.6), '小格＝開花月份，一月到十二月')
        c.setStrokeColorRGB(*MIST); c.setLineWidth(.25 * MM)
        c.line(*P(x, M + 10.6), *P(x + cw - 12, M + 10.6))
    for i, row in enumerate(rows):
        col = i // per; y = top + (i % per) * lh
        x = cw * col + 6
        if row[0] == 'H':
            c.setFillColorRGB(*BLOOM); c.setFont(F['bold'], fs * .95)
            c.drawString(*P(x, y + lh * .74), f'{row[1]}（{row[2]}～{row[3]}）')
            continue
        p = row[1]
        c.setFillColorRGB(*BLOOM); c.setFont(F['numb'], fs * .92)
        c.drawRightString(*P(x + 7.5, y + lh * .74), str(p['no']))
        c.setFillColorRGB(*INK); c.setFont(F['body'], fs)
        nm = p['n']
        while stringWidth(nm, F['body'], fs) * 25.4 / 72 > cw - 12 - 9.5 - 15 and len(nm) > 2:
            nm = nm[:-1]
        c.drawString(*P(x + 9.5, y + lh * .74), nm)
        bw = 1.12; bx = cw * col + cw - 6 - 12 * bw
        for mth in range(1, 13):
            c.setFillColorRGB(*(LEAF if mth in p['mo'] else (0.898, 0.914, 0.878)))
            c.rect(*P(bx + (mth - 1) * bw, y + lh * .72), bw * .75 * MM, lh * .48 * MM, 0, 1)
    c.showPage()


def main():
    os.makedirs(OUT, exist_ok=True)
    pts, kroot = load()
    prj = Proj(pts)
    fresh, gone, rect = assign(pts, prj)
    base = base_from_kml(kroot, prj)
    say('底圖：' + '、'.join(f'{k} {len(v)}' for k, v in base.items() if v))
    greens, lan, ark = green_from_osm(prj)
    glass = ([ark] if ark else []) + [pl for pl, nm in base['glass']]

    sheets = []
    for s in (1, 2, 3, 4):
        sel = [p for p in pts if p['sheet'] == s]
        r0 = rect[s]
        lim = 18.0                      # 最多比 v7 範圍外擴這麼多公尺
        x0 = max(min(p['x'] for p in sel), r0[0] - lim)
        x1 = min(max(p['x'] for p in sel), r0[1] + lim)
        y0 = max(min(p['y'] for p in sel), r0[2] - lim)
        y1 = min(max(p['y'] for p in sel), r0[3] + lim)
        x0, x1 = min(x0, r0[0]), max(x1, r0[1])
        y0, y1 = min(y0, r0[2]), max(y1, r0[3])
        out_of = sum(1 for p in sel if not (x0 <= p['x'] <= x1 and y0 <= p['y'] <= y1))
        if out_of:
            say(f'  ! 第 {s} 張有 {out_of} 個點在圖框外')
        pad = 7
        x0 -= pad; x1 += pad; y0 -= pad; y1 += pad
        asp = (PW - 2 * M) / MAPH
        if (x1 - x0) / (y1 - y0) < asp:
            nw = (y1 - y0) * asp; cx = (x0 + x1) / 2; x0, x1 = cx - nw / 2, cx + nw / 2
        else:
            nh = (x1 - x0) / asp; cy = (y0 + y1) / 2; y0, y1 = cy - nh / 2, cy + nh / 2
        inbox = lambda pl: (x0 <= sum(q[0] for q in pl) / len(pl) <= x1
                            and y0 <= sum(q[1] for q in pl) / len(pl) <= y1)
        myglass = [g for g in glass if inbox(g)]
        mylan = lan if (lan and inbox(lan)) else None
        def band(sub):
            """室內的號碼在 v7 是連號的；取最長的那一段，零星落在屋頂下的照樣當室外"""
            ns = sorted(p['no'] for p in sub)
            best = cur = [ns[0]] if ns else []
            for a, b in zip(ns, ns[1:]):
                if b - a <= 8:
                    cur.append(b)
                else:
                    best = cur if len(cur) > len(best) else best; cur = [b]
            best = cur if len(cur) > len(best) else best
            return (best[0], best[-1]) if best else None

        grp = {'室外': [], '蘭房內': [], '溫室內': []}
        hit = {'蘭房內': [p for p in sel if mylan and inside((p['x'], p['y']), mylan)],
               '溫室內': [p for p in sel if any(inside((p['x'], p['y']), g) for g in myglass)
                       and not (mylan and inside((p['x'], p['y']), mylan))]}
        bands = {k: band(v) for k, v in hit.items() if v}
        for p in sel:
            for k in ('蘭房內', '溫室內'):
                b = bands.get(k)
                if p in hit[k] and b and b[0] <= p['no'] <= b[1]:
                    grp[k].append(p); break
            else:
                grp['室外'].append(p)
        myglass = [g for g in myglass
                   if any(inside((p['x'], p['y']), g) for p in grp['溫室內'])]
        for k in grp:
            grp[k].sort(key=lambda p: p['no'])
        rng = {}
        if grp['溫室內']:
            rng['溫室'] = (grp['溫室內'][0]['no'], grp['溫室內'][-1]['no'])
        if grp['蘭房內']:
            rng['蘭房'] = (grp['蘭房內'][0]['no'], grp['蘭房內'][-1]['no'])
        sheets.append(dict(no=s, name=SHEET_NAME[s], x0=x0, x1=x1, y0=y0, y1=y1,
                           out=grp['室外'], n_all=len(sel), rng=rng,
                           glass_pl=myglass if grp['溫室內'] else None,
                           lan_pl=[mylan] if (mylan and grp['蘭房內']) else None,
                           groups=[(g, grp[g]) for g in ('室外', '蘭房內', '溫室內') if grp[g]]))
        say(f"第 {s} 張　{SHEET_NAME[s]}　{len(sel)} 株　"
            + '、'.join(f'{g} {len(l)}' for g, l in sheets[-1]['groups'])
            + f"　範圍 {x1-x0:.0f}×{y1-y0:.0f} m")

    chars = set('0123456789～()（）、。，；：「」·.:/ -　©' + SITE + MAPURL + VER
                + '台北植物園花曆第張株地圖上的數字對照背面索引號碼由北往南排列放大內請看溫室和蘭房裡面只標範圍'
                + '全部花名與開花月份對折四摺可放進口袋小格一到十二公尺用編號查底資料貢獻者'
                + ''.join(p['n'] for p in pts) + ''.join(SHEET_NAME.values())
                + ''.join(nm for k in base for _, nm in base[k] if nm))
    chars |= set('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ')
    F = make_fonts(chars)
    qr = os.path.join(OUT, 'qr.png')
    try:
        import qrcode
        qrcode.make(MAPURL).save(qr)
    except Exception as e:
        say(f'  ! QR：{e}'); qr = None

    from reportlab.pdfgen import canvas
    pdf = os.path.join(OUT, '口袋地圖.pdf')
    c = canvas.Canvas(pdf, pagesize=(PW * MM, PH * MM))
    c.setTitle('台北植物園花曆口袋地圖')
    for s in sheets:
        draw_map(c, s, base, greens, F, qr)
        draw_index(c, s, F)
    c.save()
    bad = sum(s.get('fail', 0) for s in sheets)
    say(f'\n{pdf}　八頁（四張 A3 雙面）'
        + ('　所有號碼都排得開' if not bad else f'　{bad} 個號碼擠在一起'))

    pn = collections.defaultdict(list)
    for p in pts:
        pn[p['code']].append((p['sheet'], p['no']))
    f2 = os.path.join(OUT, '印刷編號.csv')
    with open(f2, 'w', encoding='utf-8-sig', newline='') as fh:
        w = csv.writer(fh); w.writerow(['內部代號', '印刷編號', '說明'])
        for code in sorted(pn):
            w.writerow([code, '、'.join(f'{s}-{n}' for s, n in sorted(pn[code])), ''])
    say(f'{f2}　{len(pn)} 個代號')
    f3 = os.path.join(OUT, '編號異動.csv')
    with open(f3, 'w', encoding='utf-8-sig', newline='') as fh:
        w = csv.writer(fh); w.writerow(['異動', '印刷編號', '內部代號', '中文名'])
        for p in sorted(fresh, key=lambda q: (q['sheet'], q['no'])):
            w.writerow(['新增', f"{p['sheet']}-{p['no']}", p['code'], p['n']])
        for n, code in sorted(gone):
            w.writerow(['退掉', n, code, ''])
    say(f'{f3}　新增 {len(fresh)}、退掉 {len(gone)}')


if __name__ == '__main__':
    main()
