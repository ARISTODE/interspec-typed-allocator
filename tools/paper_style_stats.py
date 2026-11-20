#!/usr/bin/env python3
"""Style statistics of prose samples (sentence length, paragraph length, connectives, punctuation).
usage: style_stats.py NAME=FILE ...   FILE is plain text with blank lines between paragraphs."""
import re, sys, statistics as st, json
TRANS = ['However','Therefore','Thus','Moreover','Furthermore','In contrast','For example','For instance','Specifically','In particular',
         'Similarly','Additionally','In addition','First','Second','Third','Finally','Hence','Consequently','Instead','Unfortunately',
         'Note that','To this end','As a result','Nevertheless','Yet','While','Although','Since','Because','Then','Also','Likewise','Conversely','Overall','Indeed','Still']
HEDGE = ['may','might','can','could','typically','often','generally','likely','potentially','possibly','usually','appears','suggests','seems','in principle']
def sentences(par):
    par = re.sub(r'\s+', ' ', par).strip()
    par = re.sub(r'\b(e\.g|i\.e|et al|cf|vs|Fig|Sec|Eq|resp|etc)\.', lambda m: m.group(0).replace('.', '<DOT>'), par)
    out = [s.replace('<DOT>', '.').strip() for s in re.split(r'(?<=[.!?])\s+(?=[A-Z(\[“"])', par)]
    return [s for s in out if len(s.split()) >= 4]
def stats(text):
    pars = [p for p in re.split(r'\n\s*\n', text) if len(p.split()) >= 25]
    sents = [s for p in pars for s in sentences(p)]
    L = [len(s.split()) for s in sents]
    n = len(sents); words = sum(L)
    per_par = [len(sentences(p)) for p in pars]
    first = lambda s: s.lstrip('(["“')
    r = {
      'sentences': n, 'words': words,
      'sentence_len_mean': round(st.mean(L), 1), 'sentence_len_median': st.median(L), 'sentence_len_sd': round(st.pstdev(L), 1),
      'share_le_12_words': round(sum(l <= 12 for l in L) / n, 2), 'share_ge_35_words': round(sum(l >= 35 for l in L) / n, 2),
      'sentences_per_paragraph_mean': round(st.mean(per_par), 1), 'sentences_per_paragraph_median': st.median(per_par),
      'words_per_paragraph_mean': round(words / len(pars)),
      'per_100_sentences': {
        'semicolon': round(100 * sum(s.count(';') for s in sents) / n, 1),
        'colon': round(100 * sum(len(re.findall(r':(?!\d)', s)) for s in sents) / n, 1),
        'parenthesis': round(100 * sum(s.count('(') for s in sents) / n, 1),
        'dash_aside': round(100 * sum(len(re.findall(r'—|–| -- | --- ', s)) for s in sents) / n, 1),
        'starts_with_We': round(100 * sum(first(s).startswith(('We ', 'Our ')) for s in sents) / n, 1),
        'starts_with_This_These_It': round(100 * sum(first(s).startswith(('This ', 'These ', 'It ', 'Such ')) for s in sents) / n, 1),
        'passive_approx': round(100 * sum(bool(re.search(r'\b(is|are|was|were|be|been|being)\s+(\w+ly\s+)?\w+(ed|en)\b', s)) for s in sents) / n, 1),
        'e.g._or_i.e.': round(100 * sum(len(re.findall(r'\b(e\.g\.|i\.e\.)', s)) for s in sents) / n, 1),
      },
      'sentence_openers_per_100': {k: v for k, v in sorted(((t, round(100 * sum(first(s).startswith(t + ' ') or first(s).startswith(t + ',') for s in sents) / n, 1)) for t in TRANS), key=lambda x: -x[1]) if v >= 0.4},
      'hedges_per_1000_words': {k: v for k, v in sorted(((h, round(1000 * len(re.findall(r'\b' + re.escape(h) + r'\b', ' '.join(sents))) / words, 1)) for h in HEDGE), key=lambda x: -x[1]) if v >= 0.3},
    }
    return r
out = {}
for arg in sys.argv[1:]:
    name, f = arg.split('=', 1)
    out[name] = stats(open(f, encoding='utf-8', errors='replace').read())
print(json.dumps(out, indent=1))
