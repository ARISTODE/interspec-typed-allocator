import cpp
predicate vpxFile(File f) { f.getRelativePath().regexpMatch("(benchmarks/libvpx|build/libvpx-1\\.15\\.2)/.*") }
from File user, int calls, int accesses
where
  user.getRelativePath().matches("benchmarks/ffmpeg/%") and
  calls = count(FunctionCall c | c.getFile() = user and vpxFile(c.getTarget().getFile())) and
  accesses = count(FieldAccess a | a.getFile() = user and vpxFile(a.getTarget().getFile())) and
  calls + accesses > 0
select user.getRelativePath(), calls, accesses
