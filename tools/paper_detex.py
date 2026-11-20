#!/usr/bin/env python3
"""Rough plain text of the paper's body .tex files, one paragraph per block. usage: detex.py TEXDIR OUT [--keep-appendix]"""
import re, sys
d, out = sys.argv[1], sys.argv[2]
order = ['intro','background','threat_model','civ_taxonomy_mitigation','policy_inference_and_impl','eval','limitation','conclusion']
res = []
for f in order:
    t = open(f'{d}/{f}.tex', encoding='utf-8').read()
    t = '\n'.join(l for l in t.split('\n') if not l.lstrip().startswith('%'))
    t = re.sub(r'(?<!\\)%.*', '', t)
    t = re.sub(r'\\begin\{(comment|minted|figure\*?|table\*?|tikzpicture|tcolorbox|equation|listing)\}.*?\\end\{\1\}', '\n\n', t, flags=re.S)
    for c in ('trent','hamed','gtan','yongzhe','kaiming'):
        for _ in range(3): t = re.sub(r'\\' + c + r'\{[^{}]*\}', '', t)
    t = re.sub(r'\\(sub)*section\*?\{[^}]*\}|\\label\{[^}]*\}', '\n\n', t)
    t = re.sub(r'\\paragraph\{([^{}]*(\{[^{}]*\}[^{}]*)*)\}', r'\n\n', t)
    t = re.sub(r'~?\\cite\{[^}]*\}', '', t)
    t = re.sub(r'\\(ref|autoref)\{[^}]*\}', 'X', t)
    t = re.sub(r'\\(begin|end)\{(itemize|enumerate)\}|\\item', '\n\n', t)
    t = t.replace('\\sysName{}', 'InterSpec').replace('\\vulName{}', 'CIV').replace('\\%', '%').replace('\\,', ' ').replace('~', ' ').replace('\\_', '_')
    t = re.sub(r'\$[^$]*\$', 'X', t)
    for _ in range(4): t = re.sub(r'\\[a-zA-Z]+\*?(\[[^\]]*\])?\{([^{}]*)\}', r'\2', t)
    t = re.sub(r'\\[a-zA-Z]+\*?', '', t).replace('{', '').replace('}', '')
    res.append(t)
txt = '\n\n'.join(res)
txt = re.sub(r'[ \t]+', ' ', txt); txt = re.sub(r'\n[ \t]*\n\s*', '\n\n', txt)
open(out, 'w').write(txt)
