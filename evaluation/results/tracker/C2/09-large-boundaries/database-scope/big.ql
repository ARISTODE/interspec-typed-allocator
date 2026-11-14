import cpp
from Function f, int n
where n = count(Expr e | e.getEnclosingFunction() = f) and n > 8000
select f.getFile().getRelativePath(), f.getName(), n order by n desc
