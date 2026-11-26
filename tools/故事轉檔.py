#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
把 WordPress（Q故事）的匯出檔轉成網站用的 src/stories.json。

這是一次性的搬家程式。Q故事的主機要退租了，所以跑過一次、確認結果之後
就不會再用到，留著只是為了讓你知道那 93 篇是怎麼來的。

用法：
    python3 tools/故事轉檔.py ~/Documents/花曆更新/故事/q.WordPress.2026-11-26.xml

花名是怎麼認出來的：小花老師在每篇文末用「＃半邊蓮」這種井字標記寫下照片裡的花，
93 篇全部都有。所以直接讀那些標記，不去猜內文——內文裡出現「含笑」也可能是
「面帶含笑」，標記不會有這個問題。
"""
import sys, os, re, json, html
import xml.etree.ElementTree as ET

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NS = {'wp': 'http://wordpress.org/export/1.2/',
      'content': 'http://purl.org/rss/1.0/modules/content/'}
UP = 'https://qstory.timestory.club/wp-content/uploads/'


def text(el, path):
    return (el.findtext(path, default='', namespaces=NS) or '').strip()


def clean(body):
    """Gutenberg 的區塊註解拿掉，只留乾淨的 HTML，圖片網址改指向本站。"""
    s = re.sub(r'<!--\s*/?wp:[^>]*?-->', '', body)
    s = s.replace(UP, '/s/')
    s = re.sub(r'\sclass="[^"]*"', '', s)          # WordPress 的 class 用不到
    s = re.sub(r'\s(?:id|data-id|srcset|sizes)="[^"]*"', '', s)
    s = re.sub(r'<p>\s*[#＃][^<]*</p>', '', s)      # 文末的 ＃花名 另外呈現，不留在內文
    s = re.sub(r'\n{3,}', '\n\n', s)
    return s.strip()


def tags_of(body):
    """文末的 ＃標記。＋、（、，等等都當成分隔，不要黏在一起。"""
    plain = html.unescape(re.sub(r'<[^>]+>', '\n', body))
    out = []
    for t in re.findall(r'[#＃]\s*([^\s#＃]+)', plain):
        for part in re.split(r'[＋+（(，,、）)]', t):
            part = part.strip()
            if part and part not in out:
                out.append(part)
    return out


def main(xml_path):
    root = ET.parse(xml_path).getroot()
    items = root.findall('./channel/item')

    names = {s['n'] for s in json.load(
        open(os.path.join(ROOT, 'src/data/tpbg.json'), encoding='utf-8'))}
    try:
        alias = json.load(open(os.path.join(ROOT, 'tools/aliases.json'), encoding='utf-8'))
    except Exception:
        alias = {}

    att = {}
    for i in items:
        if text(i, 'wp:post_type') == 'attachment':
            url = text(i, 'wp:attachment_url')
            att[text(i, 'wp:post_id')] = {
                't': (i.findtext('title') or '').strip(),
                'f': url.replace(UP, '') if url.startswith(UP) else '',
            }

    stories, unknown = [], {}
    for i in items:
        if text(i, 'wp:post_type') != 'post' or text(i, 'wp:status') != 'publish':
            continue
        body = i.findtext('content:encoded', default='', namespaces=NS) or ''
        meta = {text(m, 'wp:meta_key'): text(m, 'wp:meta_value')
                for m in i.findall('wp:postmeta', NS)}
        cover = att.get(meta.get('_thumbnail_id', ''), {})

        flowers, other = [], []
        for t in tags_of(body):
            n = alias.get(t, t)
            (flowers if n in names else other).append(n)
            if n not in names:
                unknown.setdefault(n, []).append(i.findtext('title'))

        stories.append({
            'id': text(i, 'wp:post_name'),
            't': i.findtext('title') or '',
            'd': text(i, 'wp:post_date')[:10],
            'c': [c.text for c in i.findall('category') if c.get('domain') == 'category'],
            'cv': cover.get('f', ''),
            'ct': cover.get('t', ''),
            'f': flowers,          # 對得上主檔的花
            'o': other,            # 對不上的（園外的花、昆蟲、別名）
            'h': clean(body),
        })

    stories.sort(key=lambda s: s['d'], reverse=True)
    out = os.path.join(ROOT, 'src/stories.json')
    json.dump(stories, open(out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

    nf = sum(1 for s in stories if s['f'])
    links = len({(s['id'], f) for s in stories for f in s['f']})
    sp = len({f for s in stories for f in s['f']})
    print(f'{len(stories)} 篇寫到 {out}')
    print(f'  有對上主檔花名的：{nf} 篇，共 {links} 組對應，涉及 {sp} 種花')
    print(f'  對不上的標記 {len(unknown)} 個（園外的花、昆蟲、或主檔沒收）：')
    print('    ' + '、'.join(sorted(unknown)))


if __name__ == '__main__':
    if len(sys.argv) < 2:
        sys.exit('用法：python3 tools/故事轉檔.py <WordPress 匯出的 .xml>')
    main(sys.argv[1])
