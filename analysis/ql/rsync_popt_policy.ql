import cpp

/**
 * P4/P5 policy inference for the real rsync/popt boundary.
 *
 * In addition to the expected allocation/use type facts, P5 records the exact
 * malloc source span.  The generator can therefore instrument the analyzed
 * call itself instead of relying on a function-specific source pattern.
 */

predicate poptContextAllocation(string name, string typeName,
                                string functionName, int offset, int bytes,
                                int startLine, int startColumn,
                                int endLine, int endColumn) {
  exists(FunctionCall call, SizeofOperator size, Type objectType, Function f |
    f = call.getEnclosingFunction() and
    f.getFile().getRelativePath() = "popt/popt.c" and
    f.hasName("poptGetContext") and
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

predicate poptOptArgAllocation(string name, string typeName,
                               string functionName, int offset, int bytes,
                               int startLine, int startColumn,
                               int endLine, int endColumn) {
  exists(FunctionCall call, Function f |
    f = call.getEnclosingFunction() and
    f.getFile().getRelativePath() = "popt/popt.c" and
    f.hasName("expandNextArg") and
    call.getTarget().hasName("malloc") and
    name = f.getName() and
    typeName = "char" and
    functionName = f.getName() and
    offset = 0 and
    bytes = 1 and
    startLine = call.getLocation().getStartLine() and
    startColumn = call.getLocation().getStartColumn() and
    endLine = call.getLocation().getEndLine() and
    endColumn = call.getLocation().getEndColumn()
  )
}

predicate realPoptAllocation(string name, string typeName, string functionName,
                             int offset, int bytes, int startLine,
                             int startColumn, int endLine, int endColumn) {
  poptContextAllocation(name, typeName, functionName, offset, bytes,
                        startLine, startColumn, endLine, endColumn)
  or
  poptOptArgAllocation(name, typeName, functionName, offset, bytes,
                       startLine, startColumn, endLine, endColumn)
}

predicate assignedFromPoptGetOptArg(Variable v, Function f) {
  exists(AssignExpr assign, VariableAccess lhs, FunctionCall call |
    assign.getFile().getRelativePath() = "options.c" and
    assign.getEnclosingFunction() = f and
    lhs = assign.getLValue() and
    lhs.getTarget() = v and
    call = assign.getRValue() and
    call.getTarget().hasName("poptGetOptArg")
  )
}

predicate realTrustedUse(string name, string typeName, string functionName,
                         int offset, int bytes) {
  exists(PointerDereferenceExpr deref, VariableAccess operand, Variable v,
         Function f |
    deref.getFile().getRelativePath() = "options.c" and
    f = deref.getEnclosingFunction() and
    operand = deref.getOperand() and
    operand.getTarget() = v and
    assignedFromPoptGetOptArg(v, f) and
    name = "popt_opt_arg_first_byte" and
    typeName = "char" and
    functionName = f.getName() and
    offset = 0 and
    bytes = 1
  )
}

from string kind, string name, string typeName, string functionName,
     int offset, int bytes, int startLine, int startColumn, int endLine,
     int endColumn
where
  (kind = "allocation" and
   realPoptAllocation(name, typeName, functionName, offset, bytes, startLine,
                      startColumn, endLine, endColumn))
  or
  (kind = "use" and
   realTrustedUse(name, typeName, functionName, offset, bytes) and
   startLine = 0 and startColumn = 0 and endLine = 0 and endColumn = 0)
select kind, name, typeName, functionName, offset, bytes,
       startLine, startColumn, endLine, endColumn