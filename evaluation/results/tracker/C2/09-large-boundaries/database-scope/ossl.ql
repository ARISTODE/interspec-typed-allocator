import cpp
from string top, int nf, int ne
where
  top = any(File fl | fl.getRelativePath().matches("benchmarks/openssl/%") | fl.getRelativePath().regexpCapture("benchmarks/openssl/([^/]+)/.*", 1)) and
  nf = count(Function f | f.getFile().getRelativePath().matches("benchmarks/openssl/" + top + "/%") and exists(f.getBlock())) and
  ne = count(Expr e | e.getFile().getRelativePath().matches("benchmarks/openssl/" + top + "/%"))
select top, nf, ne order by nf desc
