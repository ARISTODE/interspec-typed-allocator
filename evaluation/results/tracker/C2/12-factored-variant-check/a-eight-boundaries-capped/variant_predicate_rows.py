#!/usr/bin/env python3
"""Rows of the predicates added by the query variants (names starting with c2)
in CodeQL evaluator logs. usage: c2rows.py LABEL=LOG[,LOG...] ...
Prints one line per label and predicate: the largest final row count over the
logs of that label ("Created relation ... with N rows")."""
import re, sys
pat = re.compile(r'Created relation \S*?::(c2[A-Za-z]+)/\d+#[0-9a-f]+/\d+@\S+ with (\d+) rows')
table, names = {}, []
for arg in sys.argv[1:]:
    label, logs = arg.split('=', 1)
    rows = {}
    for log in logs.split(','):
        for line in open(log, errors='replace'):
            m = pat.search(line)
            if m:
                rows[m.group(1)] = max(rows.get(m.group(1), 0), int(m.group(2)))
                if m.group(1) not in names: names.append(m.group(1))
    table[label] = rows
labels = list(table)
print('predicate,' + ','.join(labels))
for n in names:
    print(n + ',' + ','.join(str(table[l].get(n, '')) for l in labels))
