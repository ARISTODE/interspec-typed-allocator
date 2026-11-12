"""Reject joining corrected/legacy or different-seed profile evidence."""
import json,subprocess,sys,tempfile
from pathlib import Path
root=Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory() as d:
 p=Path(d); micro=[{'metric':'check_live','population':2,'threads':1,'ns_per_op_median':1,'ns_per_op_min':1,'ns_per_op_max':1}]
 (p/'micro.json').write_text(json.dumps(micro))
 for a,b,ok in [({}, {}, True),({'workload_mode':'independent-v1','workload_seed':7},{},False),({'workload_mode':'independent-v1','workload_seed':7},{'workload_mode':'independent-v1','workload_seed':8},False),({'workload_mode':'independent-v1','workload_seed':7},{'workload_mode':'independent-v1','workload_seed':7},True)]:
  (p/'matrix.json').write_text(json.dumps({'scenarios':[],'variants':[],**a}));(p/'checks.json').write_text(json.dumps([{'name':'test',**b}]))
  r=subprocess.run([sys.executable,str(root/'tools/render_memcached_overhead_study.py'),'--matrix',str(p/'matrix.json'),'--checks',str(p/'checks.json'),'--microbench',str(p/'micro.json'),'--output',str(p/'report.md')],capture_output=True,text=True)
  assert (r.returncode==0)==ok,r.stderr
  if not ok: assert 'mismatch' in r.stderr
print('workload metadata joining: four cases passed')
# A count-only timing table must render missing quantiles as unavailable.
with tempfile.TemporaryDirectory() as d:
 p=Path(d)
 row={'name':'test','native_ops_per_s':1,'rlbox_ops_per_s':1,'interspec_ops_per_s':1,'rlbox_loss_vs_native_pct':0,'interspec_loss_vs_native_pct':0,'interspec_loss_vs_rlbox_pct':0,'native_p99_us':None,'rlbox_p99_us':None,'interspec_p99_us':None,'valid_lossless':True}
 (p/'matrix.json').write_text(json.dumps({'scenarios':[row],'variants':[],'measurement_mode':'count-only'}));(p/'checks.json').write_text('[]');(p/'micro.json').write_text(json.dumps(micro))
 r=subprocess.run([sys.executable,str(root/'tools/render_memcached_overhead_study.py'),'--matrix',str(p/'matrix.json'),'--checks',str(p/'checks.json'),'--microbench',str(p/'micro.json'),'--output',str(p/'report.md')],capture_output=True,text=True)
 assert r.returncode==0,r.stderr
 assert 'unavailable/unavailable/unavailable' in (p/'report.md').read_text()
print('count-only latency rendering: passed')

# Deployment reports must not silently combine old and corrected workload rows,
# or attach the wrong environment provenance to a consistent set of rows.
archive = root / 'evaluation/results/memcached-deployment'
legacy = {}
corrected = {'workload_mode': 'independent-v1', 'workload_seed': 7}
cases = [
 ('historical', legacy, legacy, legacy, True),
 ('corrected', corrected, corrected, corrected, True),
 ('mixed_modes', corrected, legacy, corrected, False),
 ('mixed_seeds', corrected, {**corrected, 'workload_seed': 8}, corrected, False),
 ('missing_seed', {'workload_mode': 'independent-v1'}, corrected, corrected, False),
 ('environment_mismatch', corrected, corrected, legacy, False),
 ('legacy_ignored_seed', {'workload_mode': 'legacy', 'workload_seed': 7},
  {'workload_mode': 'legacy', 'workload_seed': 8}, legacy, True),
]
for name, first, second, environment, ok in cases:
 with tempfile.TemporaryDirectory() as d:
  p = Path(d)
  for filename in ('correctness-summary.json', 'tracking-summary.json'):
   (p / filename).write_bytes((archive / filename).read_bytes())
  perf = json.loads((archive / 'performance-summary.json').read_text())
  for index, row in enumerate(perf):
   row.pop('workload_mode', None); row.pop('workload_seed', None)
   row.update(first if index == 0 else second)
  env = json.loads((archive / 'environment.json').read_text())
  env['parameters'].pop('workload_mode', None); env['parameters'].pop('workload_seed', None)
  env['parameters'].update(environment)
  (p / 'performance-summary.json').write_text(json.dumps(perf))
  (p / 'environment.json').write_text(json.dumps(env))
  r = subprocess.run([sys.executable, str(root / 'tools/render_memcached_results.py'),
                      '--results', str(p), '--output', str(p / 'report.md')],
                     capture_output=True, text=True)
  assert (r.returncode == 0) == ok, (name, r.stderr)
  if ok:
   report = (p / 'report.md').read_text()
   assert 'Workload generator: ' + first.get('workload_mode', 'legacy') in report
   if first == corrected: assert 'seed: 7' in report
  else:
   assert 'workload' in r.stderr, (name, r.stderr)
print('deployment workload metadata: seven cases passed')
