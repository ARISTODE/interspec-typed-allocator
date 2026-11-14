import cpp
from string dir, int nf, int ne
where
  dir = ["benchmarks/ffmpeg/", "benchmarks/libvpx/", "build/", "other"] and
  nf = count(Function f | (if dir = "other" then not f.getFile().getRelativePath().regexpMatch("(benchmarks|build)/.*") else f.getFile().getRelativePath().matches(dir + "%")) and exists(f.getBlock())) and
  ne = count(Expr e | if dir = "other" then not e.getFile().getRelativePath().regexpMatch("(benchmarks|build)/.*") else e.getFile().getRelativePath().matches(dir + "%"))
select dir, nf, ne
