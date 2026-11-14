import cpp
from File fl, int n
where n = count(Function f | f.getFile() = fl and exists(f.getBlock())) and fl.getRelativePath().matches("benchmarks/pcre/%") and n > 0
select fl.getRelativePath() as file, n order by file
