import cpp

/**
 * P7c policy inference for the real memcached bipbuffer source.
 *
 * bipbuf_new() allocates one flexible-array bipbuf_t object with a runtime
 * capacity. bipbuf_peek_all() later returns an interior pointer into that same
 * object together with a runtime byte extent. The trusted-use adapter records
 * that T consumes that returned range; the expected allocation type is derived
 * from the owner parameter's source type rather than from the byte-pointer
 * return type.
 */

predicate bipbufAllocation(string name, string typeName, string functionName,
                           int offset, int bytes, int startLine,
                           int startColumn, int endLine, int endColumn) {
  exists(FunctionCall call, Function f, LocalVariable v, PointerType pointerType |
    f = call.getEnclosingFunction() and
    f.getFile().getRelativePath() = "bipbuffer.c" and
    f.hasName("bipbuf_new") and
    call.getTarget().hasName("malloc") and
    v.getFunction() = f and
    v.getName() = "me" and
    v.getInitializer().getExpr().getUnconverted() = call and
    pointerType = v.getType() and
    typeName = pointerType.getBaseType().getName() and
    name = f.getName() and
    functionName = f.getName() and
    offset = 0 and
    bytes = pointerType.getBaseType().getSize() and
    startLine = call.getLocation().getStartLine() and
    startColumn = call.getLocation().getStartColumn() and
    endLine = call.getLocation().getEndLine() and
    endColumn = call.getLocation().getEndColumn()
  )
}

predicate trustedDynamicRangeUse(string name, string typeName,
                                 string functionName, int offset, int bytes) {
  exists(Function f, PointerType ownerType |
    f.getFile().getRelativePath() = "interspec_trusted_uses.c" and
    f.hasName("interspec_trusted_use_bipbuf_range") and
    f.getNumberOfParameters() = 3 and
    ownerType = f.getParameter(0).getType() and
    typeName = ownerType.getBaseType().getName() and
    name = "bipbuf_peek_all_range" and
    functionName = f.getName() and
    offset = 0 and
    bytes = 0
  )
}

from string kind, string name, string typeName, string functionName,
     int offset, int bytes, int startLine, int startColumn, int endLine,
     int endColumn
where
  (kind = "allocation" and
   bipbufAllocation(name, typeName, functionName, offset, bytes,
                    startLine, startColumn, endLine, endColumn))
  or
  (kind = "dynamic_use" and
   trustedDynamicRangeUse(name, typeName, functionName, offset, bytes) and
   startLine = 0 and startColumn = 0 and endLine = 0 and endColumn = 0)
select kind, name, typeName, functionName, offset, bytes,
       startLine, startColumn, endLine, endColumn
