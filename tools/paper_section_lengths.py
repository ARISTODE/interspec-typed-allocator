#!/usr/bin/env python3
"""Position of each section heading in a two-column PDF, in pages.
usage: section_lengths.py BBOX_HTML AUX   (BBOX_HTML from pdftotext -bbox-layout)"""
import re, sys, html
bbox, aux = sys.argv[1], sys.argv[2]
pages = re.split(r'<page ', open(bbox, encoding='utf-8').read())[1:]
lines = []  # (page, xmin, ymin, text)
dims = []
for pi, p in enumerate(pages, 1):
    w = float(re.search(r'width="([\d.]+)"', p).group(1)); h = float(re.search(r'height="([\d.]+)"', p).group(1))
    dims.append((w, h))
    for m in re.finditer(r'<line xMin="([\d.]+)" yMin="([\d.]+)" xMax="([\d.]+)" yMax="([\d.]+)">(.*?)</line>', p, re.S):
        words = re.findall(r'<word[^>]*>(.*?)</word>', m.group(5))
        lines.append((pi, float(m.group(1)), float(m.group(2)), html.unescape(' '.join(words))))
top = min(l[2] for l in lines); bottom = max(l[2] for l in lines)
def pos(l):
    page, x, y, _ = l
    col = 0 if x < dims[page-1][0] / 2 - 10 else 1
    return (page - 1) + (col + (y - top) / (bottom - top)) / 2
heads = []
for line in open(aux, encoding='utf-8', errors='replace'):
    m = re.match(r'\\@writefile\{toc\}\{\\contentsline \{(section|subsection)\}\{\\numberline \{([^}]*)\}(.*?)\}\{(\d+)\}', line)
    if m: heads.append((m.group(1), m.group(2), re.sub(r'\\[a-zA-Z]+ ?|[{}]', '', m.group(3)).strip(), int(m.group(4))))
    m = re.match(r'\\@writefile\{toc\}\{\\contentsline \{section\}\{(References|Appendix[^}]*)\}\{(\d+)\}', line)
    if m: heads.append(('section', '', m.group(1), int(m.group(2))))
out = []
for kind, num, title, page in heads:
    key = re.sub(r'\W', '', title).lower()[:18]
    cand = [l for l in lines if l[0] == page and re.sub(r'\W', '', l[3]).lower().lstrip('0123456789abcdefghi')[:len(key)] == key] or \
           [l for l in lines if l[0] == page and key in re.sub(r'\W', '', l[3]).lower()]
    out.append((kind, num, title, pos(cand[0]) if cand else float(page - 1)))
for i, (kind, num, title, p) in enumerate(out):
    nxt = next((q for k, n, t, q in out[i+1:] if kind == 'subsection' or k == 'section'), None)
    length = f'{nxt - p:5.2f}' if nxt is not None else '     '
    print(f"{'  ' if kind == 'subsection' else ''}{num:5s} {title[:58]:58s} starts {p:5.2f}  length {length}")
