import cpp

/**
 * P4 policy inference for the real rsync/popt boundary.
 *
 * The query connects two facts from the real source tree.  In U, popt allocates
 * the poptContext object and the dynamically-sized char buffer eventually
 * returned by poptGetOptArg().  In T, rsync stores that return value in a local
 * variable and later dereferences the first char through *arg.  The resulting
 * policy gives the allocator a trusted expected type and gives the trusted use
 * site a matching type/range check without inventing a semantic string bound.
 */

predicate poptContextAllocation(string name, string typeName,
                                string functionName, int offset, int bytes) {
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

predicate poptOptArgAllocation(string name, string typeName,
                               string functionName, int offset, int bytes) {
  exists(FunctionCall call, Function f |
    f = call.getEnclosingFunction() and
    f.getFile().getRelativePath() = "popt/popt.c" and
    f.hasName("expandNextArg") and
    call.getTarget().hasName("malloc") and
    name = f.getName() and
    typeName = "char" and
    functionName = f.getName() and
    offset = 0 and
    bytes = 1
  )
}

predicate realPoptAllocation(string name, string typeName, string functionName,
                             int offset, int bytes) {
  poptContextAllocation(name, typeName, functionName, offset, bytes)
  or
  poptOptArgAllocation(name, typeName, functionName, offset, bytes)
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
