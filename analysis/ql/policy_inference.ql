import cpp

predicate trackedUntrustedBoundary(Function f) {
  f.getFile().getRelativePath() = "poc/typed_poc_untrusted.c" and
  (f.hasName("typed_poc_make_item") or f.hasName("typed_poc_make_other"))
}

predicate inferredAllocation(string name, string typeName, string functionName,
                             int offset, int bytes, int startLine,
                             int startColumn, int endLine, int endColumn) {
  exists(FunctionCall call, SizeofOperator size, Type objectType, Function f |
    f = call.getEnclosingFunction() and
    trackedUntrustedBoundary(f) and
    call.getTarget().hasName("malloc") and
    size = call.getArgument(0) and
    objectType = size.getTypeOperand().getUnspecifiedType() and
    typeName = objectType.getName() and
    name = f.getName() and
    functionName = f.getName() and
    offset = 0 and
    bytes = objectType.getSize() and
    startLine = call.getLocation().getStartLine() and
    startColumn = call.getLocation().getStartColumn() and
    endLine = call.getLocation().getEndLine() and
    endColumn = call.getLocation().getEndColumn()
  )
}

predicate inferredUse(string name, string typeName, string functionName,
                      int offset, int bytes) {
  exists(PointerFieldAccess access, Field field, Function f |
    access.getFile().getRelativePath() = "analysis/poc_trusted_uses.cpp" and
    f = access.getEnclosingFunction() and
    f.getName().regexpMatch("trusted_use_.*") and
    field = access.getTarget() and
    typeName = field.getDeclaringType().getName() and
    name = typeName.toLowerCase() + "_" + field.getName() and
    functionName = f.getName() and
    offset = field.getByteOffset() and
    bytes = field.getType().getSize()
  )
}

from string kind, string name, string typeName, string functionName,
     int offset, int bytes, int startLine, int startColumn, int endLine,
     int endColumn
where
  (kind = "allocation" and
   inferredAllocation(name, typeName, functionName, offset, bytes, startLine,
                      startColumn, endLine, endColumn))
  or
  (kind = "use" and inferredUse(name, typeName, functionName, offset, bytes) and
   startLine = 0 and startColumn = 0 and endLine = 0 and endColumn = 0)
select kind, name, typeName, functionName, offset, bytes,
       startLine, startColumn, endLine, endColumn