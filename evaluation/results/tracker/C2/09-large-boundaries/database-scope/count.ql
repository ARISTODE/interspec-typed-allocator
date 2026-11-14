import cpp
from string dir, int nf, int ne
where
  dir = ["benchmarks/nginx/", "benchmarks/pcre/", "benchmarks/openssl/", "other"] and
  nf = count(Function f | (if dir = "other" then not f.getFile().getRelativePath().matches("benchmarks/%") else f.getFile().getRelativePath().matches(dir + "%")) and exists(f.getBlock())) and
  ne = count(Expr e | if dir = "other" then not e.getFile().getRelativePath().matches("benchmarks/%") else e.getFile().getRelativePath().matches(dir + "%"))
select dir, nf, ne
