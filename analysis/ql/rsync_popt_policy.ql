import cpp

/**
 * P4 policy inference for the real rsync/popt boundary.
 *
 * This query intentionally starts with one concrete trusted dereference shape:
 * rsync stores a poptGetOptArg() result in a local variable and later reads
 * the first character through *arg.  That is enough to infer the expected
 * pointee type for the first real Extended-SP3 use site without inventing a
 * semantic string bound in static analysis.
 */

predicate realPoptAllocation(string name, string typeName, string functionName,
                             int offset, int bytes) {
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
    bytes = objectType.getSize()
  )
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
     int offset, int bytes
where
  (kind = "allocation" and
   realPoptAllocation(name, typeName, functionName, offset, bytes))
  or
  (kind = "use" and
   realTrustedUse(name, typeName, functionName, offset, bytes))
select kind, name, typeName, functionName, offset, bytes
