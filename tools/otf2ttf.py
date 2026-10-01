#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 CFF（OpenType/PostScript）字型轉成 TrueType，reportlab 才嵌得進 PDF。"""
import sys
from fontTools.ttLib import TTFont, newTable
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.pens.cu2quPen import Cu2QuPen


def otf2ttf(src, dst, max_err=1.0):
    f = TTFont(src)
    if 'glyf' in f:
        f.save(dst); return dst
    gs = f.getGlyphSet()
    glyf = newTable('glyf'); glyf.glyphOrder = f.getGlyphOrder(); glyf.glyphs = {}
    for name in f.getGlyphOrder():
        pen = TTGlyphPen(gs)
        gs[name].draw(Cu2QuPen(pen, max_err, reverse_direction=True))
        glyf[name] = pen.glyph()
    f['glyf'] = glyf
    upem = f['head'].unitsPerEm
    f['loca'] = newTable('loca')
    f['maxp'] = newTable('maxp'); f['maxp'].tableVersion = 0x00010000
    f['maxp'].maxZones = 1; f['maxp'].maxTwilightPoints = 0
    f['maxp'].maxStorage = 0; f['maxp'].maxFunctionDefs = 0
    f['maxp'].maxInstructionDefs = 0; f['maxp'].maxStackElements = 0
    f['maxp'].maxSizeOfInstructions = 0; f['maxp'].maxComponentElements = 0
    f['maxp'].numGlyphs = len(glyf.glyphOrder)
    f['head'].indexToLocFormat = 0
    post = f['post']; post.formatType = 2.0
    post.extraNames = []; post.mapping = {}; post.glyphOrder = f.getGlyphOrder()
    for t in ('CFF ', 'CFF2', 'VORG'):
        if t in f:
            del f[t]
    f.sfntVersion = '\x00\x01\x00\x00'
    f.save(dst)
    return dst


if __name__ == '__main__':
    print(otf2ttf(sys.argv[1], sys.argv[2]))
