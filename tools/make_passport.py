#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
小花老師的花曆 — 拍花護照

用法（在 smallflower-web 資料夾裡執行）：
    python3 tools/make_passport.py                 # A4，一區一張（網站免費下載用）
    python3 tools/make_passport.py 荷花池 薑區      # A4，只做這幾區
    python3 tools/make_passport.py --a3            # A3 兩張雙面，全部擠在一起（寄給贊助者）
    python3 tools/make_passport.py --a3 --pages 6  # 允許多一點頁數，字就可以更大
    python3 tools/make_passport.py --split --out public/passport 荷花池 薑區
                                                   # 一區一個檔，放進網站給人下載

每一行是「☐ 地圖編號 花名」，找到或拍到就打個勾。
A3 版的字級由程式自己找：在指定頁數內塞得下的最大字。
輸出到 ~/Documents/花曆地圖/
"""
import os, sys, json, collections

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SLUG = 'tpbg'
OUT = os.path.expanduser('~/Documents/花曆地圖')
SITE = 'smallflower.tw'
MM = 72 / 25.4
BLEED = 3.0
M = 14.0
INK = (0.114, 0.227, 0.184)
LEAF = (0.357, 0.486, 0.345)
MIST = (0.863, 0.890, 0.835)
BLOOM = (0.722, 0.200, 0.416)
PAPER = (0.973, 0.973, 0.957)

sys.path.insert(0, os.path.join(ROOT, 'tools'))
from make_map import make_fonts, draw_logo                       # noqa: E402

VER = '2026 年 10 月'
FOOT = (f'小花老師的花曆　{SITE}　© 2026 小花老師　'
        '花卉記錄與編號版權所有，請勿翻印轉載。')
NOTE = '編號是「·」的，表示這一版找花地圖還沒收錄這一株。'
UI = ('拍花護照　台北植物園　種　第 頁／共 頁　找到或拍到就打個勾　'
      + NOTE + FOOT + VER + SITE + '0123456789-·／　')


def sheet_of(s):
    n = (s.get('no') or [''])[0]
    try:
        return int(n.split('-')[0])
    except Exception:
        return 9


def load(want=None):
    sp = json.load(open(os.path.join(ROOT, 'src/data', SLUG + '.json'), encoding='utf-8'))
    by = collections.defaultdict(list)
    for s in sp:
        if s.get('st') == '現存':
            by[s.get('z') or '其他'].append(s)

    def key(s):
        n = (s.get('no') or [''])[0]
        try:
            a, b = n.split('-'); return (int(a), int(b), s['n'])
        except Exception:
            return (9, 9999, s['n'])
    for z in by:
        by[z].sort(key=key)
    # 區域順序跟著地圖的張數走，走起來比較順
    order = sorted(by, key=lambda z: (collections.Counter(
        sheet_of(s) for s in by[z]).most_common(1)[0][0], -len(by[z]), z))
    if want:
        for w in want:
            if w not in by:
                print(f'  ! 找不到區域「{w}」')
        order = [z for z in order if z in want]
    return [(z, by[z]) for z in order]


def frame(c, PW, PH, F, title, right, note=False):
    c.setTrimBox((BLEED * MM, BLEED * MM, (BLEED + PW) * MM, (BLEED + PH) * MM))
    c.setBleedBox((0, 0, (PW + 2 * BLEED) * MM, (PH + 2 * BLEED) * MM))
    c.setFillColorRGB(*PAPER)
    c.rect(0, 0, (PW + 2 * BLEED) * MM, (PH + 2 * BLEED) * MM, 0, 1)
    P = lambda x, y: ((x + BLEED) * MM, (PH - y + BLEED) * MM)
    draw_logo(c, M + 6.5, M + 6.0, 13)
    c.setFillColorRGB(*LEAF); c.setFont(F['body'], 8)
    c.drawString(*P(M + 16, M + 3.4), '台北植物園　拍花護照')
    c.setFillColorRGB(*INK); c.setFont(F['bold'], 17)
    c.drawString(*P(M + 16, M + 11.4), title)
    c.setFillColorRGB(*LEAF); c.setFont(F['body'], 8)
    c.drawRightString(*P(PW - M, M + 11.4), right)
    c.drawRightString(*P(PW - M, M + 3.4), '找到或拍到就打個勾')
    c.setStrokeColorRGB(*MIST); c.setLineWidth(.3 * MM)
    c.line(*P(M, M + 15.5), *P(PW - M, M + 15.5))
    c.setFillColorRGB(*LEAF); c.setFont(F['body'], 5.8)
    c.drawString(*P(M, PH - M + 2.5), FOOT)
    c.drawRightString(*P(PW - M, PH - M + 2.5), VER)
    if note:
        c.setFont(F['body'], 6)
        c.drawString(*P(M, PH - M - 2.5), NOTE)
    return P


def row(c, P, F, s, x, y, fs, nox, room, stringWidth):
    bs = 3.3 * fs / 8
    c.setStrokeColorRGB(*LEAF); c.setLineWidth(.22 * MM)
    c.rect(*P(x, y + bs + .2), bs * MM, bs * MM, 1, 0)
    no = (s.get('no') or [''])[0]
    c.setFillColorRGB(*BLOOM); c.setFont(F['numb'], fs * .88)
    c.drawString(*P(x + bs + 1.7, y + bs), no or '·')
    c.setFillColorRGB(*INK)
    nm = s['n']
    # 欄寬是照大多數花名算的，少數特別長的（加勒比海盜秋海棠、達爾馬提亞風鈴草）
    # 塞不下。以前是直接把後面的字切掉，印出來就變成「加勒比海盜秋海」——
    # 清單上少一個字等於另一種花，寧可把那一行的字縮小一點也要印完整。
    f2 = fs
    while stringWidth(nm, F['body'], f2) * 25.4 / 72 > room and f2 > fs * 0.68:
        f2 -= fs * 0.02
    c.setFont(F['body'], f2)
    while stringWidth(nm, F['body'], f2) * 25.4 / 72 > room and len(nm) > 2:
        nm = nm[:-1]
    c.drawString(*P(x + nox, y + bs), nm)


def main():
    from reportlab.pdfgen import canvas
    from reportlab.pdfbase.pdfmetrics import stringWidth
    args = [a for a in sys.argv[1:]]
    a3 = '--a3' in args
    if a3:
        args.remove('--a3')
    split = '--split' in args
    if split:
        args.remove('--split')
    outdir = OUT
    if '--out' in args:
        i = args.index('--out')
        outdir = args[i + 1]
        if not os.path.isabs(outdir):
            outdir = os.path.join(ROOT, outdir)
        del args[i:i + 2]
    want_pages = 4
    if '--pages' in args:
        i = args.index('--pages'); want_pages = int(args[i + 1]); del args[i:i + 2]
    zones = load(args or None)
    if not zones:
        print('沒有要做的區域。'); sys.exit(1)
    os.makedirs(outdir, exist_ok=True)

    chars = set(UI) | {c for _, g in zones for s in g for c in s['n']} \
        | {c for z, _ in zones for c in z}
    chars |= set('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ.:/ ')
    F = make_fonts(chars)
    allsp = [s for _, g in zones for s in g]

    def plan(PW, PH, fs, head):
        """算出這個字級下的欄寬、欄數、行數"""
        bs = 3.3 * fs / 8
        nox = bs + 1.7 + stringWidth('8-888', F['numb'], fs * .88) * 25.4 / 72 + 2.0
        w = sorted(stringWidth(s['n'], F['body'], fs) * 25.4 / 72 for s in allsp)
        room = w[int(len(w) * 0.985)]             # 最長的 1.5% 截掉，不要為它們拉寬整欄
        cw = nox + room + 2.5
        gut = 4.0
        cols = int((PW - 2 * M + gut) // (cw + gut))
        lh = fs * 0.625
        rows = int((PH - 2 * M - head - 9) // lh)
        over = sum(1 for x in w if x > room)
        return dict(fs=fs, nox=nox, room=room, cw=cw, gut=gut,
                    cols=cols, lh=lh, rows=rows, cap=cols * rows, over=over)

    def fill(PW, PH, n, head, pages=1, maxfs=13.0):
        """把 n 行塞滿整頁：試每一種欄數，挑字能放最大的那一個"""
        W = PW - 2 * M
        H = PH - 2 * M - head - 9
        best = None
        for cols in range(1, 9):
            rows = -(-n // (cols * pages))
            if rows < 1:
                continue
            fs = min(maxfs, (H / rows) / 0.625)
            if fs < 6:
                continue
            L = plan(PW, PH, fs, head)            # 這個字級下一欄要多寬
            if L['cw'] + L['gut'] > W / cols + L['gut'] - 0.1:
                continue                          # 這麼多欄放不下
            cw = (W - L['gut'] * (cols - 1)) / cols
            # 欄變寬了，花名可以用的寬度也要跟著放寬，不然白白截字
            L = dict(L, cols=cols, rows=rows, cap=cols * rows, cw=cw,
                     room=max(L['room'], cw - L['nox'] - 2.5))
            if best is None or L['fs'] > best['fs']:
                best = L
        return best

    if not a3:
        # ---------- A4：一區一張，網站免費下載 ----------
        PW, PH = 210.0, 297.0
        groups = [[(z, g)] for z, g in zones] if split else [zones]
        for grp in groups:
            name = '拍花護照' + (f'_{grp[0][0]}' if split else '') + '.pdf'
            pdf = os.path.join(outdir, name)
            cv = canvas.Canvas(pdf, pagesize=((PW + 2 * BLEED) * MM, (PH + 2 * BLEED) * MM))
            cv.setTitle('台北植物園 拍花護照'); cv.setAuthor('小花老師')
            n = 0
            for z, g in grp:
                # 一區一張：讓字放到最大，排滿整頁；真的塞不下才用第二頁
                LY = None
                for np in (1, 2, 3):
                    LY = fill(PW, PH, len(g), 22, pages=np)
                    if LY and LY['fs'] >= (9.0 if np == 1 else 7.5):
                        break
                if not LY:
                    LY = plan(PW, PH, 8.0, 22)
                pages = [g[i:i + LY['cap']] for i in range(0, len(g), LY['cap'])] or [[]]
                for pi, chunk in enumerate(pages, 1):
                    n += 1
                    tail = f'{len(g)} 種' + (f'　第 {pi} 頁／共 {len(pages)} 頁'
                                            if len(pages) > 1 else '')
                    P = frame(cv, PW, PH, F, z, tail,
                              note=any(not (s.get('no') or [''])[0] for s in chunk))
                    rows = -(-len(chunk) // LY['cols'])      # 最後一頁也排得平均
                    for i, s in enumerate(chunk):
                        col, r = divmod(i, rows)
                        row(cv, P, F, s, M + col * (LY['cw'] + LY['gut']),
                            M + 22 + r * LY['lh'], LY['fs'], LY['nox'], LY['room'],
                            stringWidth)
                    cv.showPage()
                if split:
                    print(f"{pdf}　A4 {n} 頁、{len(g)} 種"
                          f"（{LY['fs']:.1f}pt、{LY['cols']} 欄 × {LY['rows']} 行）")
            cv.save()
            if not split:
                print(f"{pdf}　A4 {n} 頁、{sum(len(g) for _, g in grp)} 種")
        return

    # ---------- A3：兩張雙面，全部排在一起 ----------
    PW, PH = 297.0, 420.0
    HEAD = 22
    items = []                       # ('H', 區名, 幾種) 或 ('R', 花)
    for z, g in zones:
        items.append(('H', z, len(g)))
        items += [('R', s) for s in g]

    pick = None
    for fs in [11, 10.5, 10, 9.5, 9, 8.5, 8, 7.5, 7]:
        L = plan(PW, PH, fs, HEAD)
        if L['cols'] < 1 or L['rows'] < 6:
            continue
        # 區標題佔兩行，而且不能落在欄位最底下變成孤行
        col, r, n = 0, 0, 1
        ok = True
        for k, it in enumerate(items):
            need = 2 if it[0] == 'H' else 1
            if it[0] == 'H' and r + 2 + 3 > L['rows']:
                need = L['rows'] - r          # 擠不下標題＋三行就換下一欄
            if r + need > L['rows']:
                col += 1; r = 0
                if col >= L['cols']:
                    col = 0; n += 1
                    if n > want_pages:
                        ok = False; break
                need = 2 if it[0] == 'H' else 1
            it_rows = 2 if it[0] == 'H' else 1
            r += it_rows
        if ok:
            pick = (L, n); break
    if not pick:
        print(f'{want_pages} 頁排不下，加 --pages 讓它多幾頁。'); sys.exit(1)
    L, npages = pick

    pdf = os.path.join(OUT, '拍花護照_A3.pdf')
    c = canvas.Canvas(pdf, pagesize=((PW + 2 * BLEED) * MM, (PH + 2 * BLEED) * MM))
    c.setTitle('台北植物園 拍花護照（A3 完整版）'); c.setAuthor('小花老師')
    col, r, page = 0, 0, 1
    P = frame(c, PW, PH, F, '台北植物園 全園', f'{len(allsp)} 種　第 1 頁／共 {npages} 頁', note=True)
    for it in items:
        need = 2 if it[0] == 'H' else 1
        if it[0] == 'H' and r + 5 > L['rows']:
            r = L['rows']
        if r + need > L['rows']:
            col += 1; r = 0
            if col >= L['cols']:
                c.showPage(); page += 1; col = 0
                P = frame(c, PW, PH, F, '台北植物園 全園',
                          f'{len(allsp)} 種　第 {page} 頁／共 {npages} 頁', note=True)
        x = M + col * (L['cw'] + L['gut'])
        y = M + HEAD + r * L['lh']
        if it[0] == 'H':
            c.setFillColorRGB(*BLOOM); c.setFont(F['bold'], L['fs'] * 1.05)
            c.drawString(*P(x, y + L['lh'] * .9), f'{it[1]}')
            c.setFont(F['body'], L['fs'] * .8); c.setFillColorRGB(*LEAF)
            c.drawRightString(*P(x + L['cw'] - 1, y + L['lh'] * .9), f'{it[2]}')
            c.setStrokeColorRGB(*MIST); c.setLineWidth(.25 * MM)
            c.line(*P(x, y + L['lh'] * 1.35), *P(x + L['cw'] - 1, y + L['lh'] * 1.35))
            r += 2
        else:
            row(c, P, F, it[1], x, y, L['fs'], L['nox'], L['room'], stringWidth)
            r += 1
    c.showPage(); c.save()
    print(f"{pdf}　A3 {page} 頁（{(page + 1) // 2} 張雙面）、{len(zones)} 區、{len(allsp)} 種")
    print(f"　字級 {L['fs']}pt、{L['cols']} 欄 × {L['rows']} 行、欄寬 {L['cw']:.1f}mm"
          f"（最長的 {L['over']} 個花名會自動縮小字級，不會被截掉）")


if __name__ == '__main__':
    main()
