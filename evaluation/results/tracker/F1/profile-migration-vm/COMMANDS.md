# Focused VM commands

Executed on the exact local VM code commit in `source-commit.txt` after integrating the
concurrent branch through `f904ae6`. All four commands returned zero.

```sh
python3 tests/memcached_current_profile.py
python3 tests/memcached_corrected_profile.py
python3 tests/memcached_profile_evidence.py
python3 tests/memcached_workload_metadata.py
```

Also passed: AST parsing of the seven changed/new Python files, PyYAML parsing
of both changed workflows, `bash -n scripts/run_memcached_profile.sh`, and
`git diff --check`. There was no broad test suite, application collection,
security/fault test, hosted dispatch, controlled measurement or paper edit.
