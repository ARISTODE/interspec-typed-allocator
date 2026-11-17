/**
 * @name R5: assignments to the pointer slots of the interface parameters
 * @id interspec-r5-slot-writes
 * @description For every interface parameter and slot path, the assignments
 *   that the target-domain rules look at (PointerTargetDomain::slotMayTargetT,
 *   slotMayTargetU and slotMayTargetNull): an assignment in the interface
 *   function, or in a function of U called from it through at most three
 *   calls that pass a carrier of the slot. Unlike those rules, this query
 *   reports the assignment whatever its right-hand side is, with the kind of
 *   the right-hand side and whether the rules classify it. Tracker item R5:
 *   run in the query pack of the variant r5_ten_functions, which restricts
 *   the interface to the ten functions.
 * @kind table
 */

import cpp
import lib.PointerBoundaryBase
import lib.PointerSlotUnified
import lib.TUntrustedConfig
import lib.InterCompartmentFlow
import lib.PointerTargetDomain

/** The condition on the left-hand side used by the target-domain rules. */
predicate slotAssignment(Parameter param, string path, Assignment assign) {
  assign.getEnclosingFunction() = param.getFunction() and
  not (
    assign.getLValue() instanceof VariableAccess and
    not assign.getLValue() instanceof FieldAccess
  ) and
  PointerSlotUnified::exprPathForParameter(param, assign.getLValue(), path)
}

/** `param` or something reached from it at `parentPath` is passed to `calleeParam` in U. */
predicate passedTo(Parameter param, string parentPath, Parameter calleeParam) {
  exists(FunctionCall call, int i, Expr argExpr, Expr carrier |
    call.getEnclosingFunction() = param.getFunction() and
    PointerBoundaryBase::isUntrustedFile(call.getTarget().getFile()) and
    calleeParam = call.getTarget().getParameter(i) and
    exists(Type t, PointerType pt |
      t = calleeParam.getType() and PointerSlotUnified::pointerType(t, pt)
    ) and
    argExpr = call.getArgument(i) and
    PointerBoundaryBase::exprContains(argExpr, carrier) and
    PointerSlotUnified::exprPathForParameter(param, carrier, parentPath)
  )
}

predicate helperWrite(Parameter param, string path, Assignment assign, int calls) {
  slotAssignment(param, path, assign) and calls = 0
  or
  exists(Parameter callee, string parentPath, string subPath, int below |
    passedTo(param, parentPath, callee) and
    helperWrite(callee, subPath, assign, below) and
    below < 2 and
    path = parentPath + subPath and
    calls = below + 1
  )
}

predicate interfaceWrite(
  PointerBoundaryBase::BoundaryParameter p, string path, Assignment assign, int calls
) {
  p.direction("T_TO_U") and
  (
    assign.getEnclosingFunction() = p.getFunction() and
    not (
      assign.getLValue() instanceof VariableAccess and
      not assign.getLValue() instanceof FieldAccess
    ) and
    PointerSlotUnified::exprPath(p, assign.getLValue(), path) and
    calls = 0
    or
    exists(
      FunctionCall call, int i, Parameter helperParam, string parentPath, string subPath,
      Expr argExpr, Expr carrier, int below
    |
      call.getEnclosingFunction() = p.getFunction() and
      helperParam = call.getTarget().getParameter(i) and
      exists(Type t, PointerType pt |
        t = helperParam.getType() and PointerSlotUnified::pointerType(t, pt)
      ) and
      PointerBoundaryBase::isUntrustedFile(call.getTarget().getFile()) and
      argExpr = call.getArgument(i) and
      PointerBoundaryBase::exprContains(argExpr, carrier) and
      PointerSlotUnified::exprPath(p, carrier, parentPath) and
      helperWrite(helperParam, subPath, assign, below) and
      path = parentPath + subPath and
      subPath != "" and
      calls = below + 1
    )
  )
}

string calleeName(Expr rhs) {
  result = rhs.(FunctionCall).getTarget().getName()
  or
  not rhs instanceof FunctionCall and result = ""
}

from
  PointerBoundaryBase::BoundaryParameter p, string path, Assignment assign, int calls, Expr rhs,
  Function writer, int t, int u, int n
where
  interfaceWrite(p, path, assign, calls) and
  rhs = assign.getRValue() and
  writer = assign.getEnclosingFunction() and
  (
    PointerTargetDomain::exprMayTargetTFromBoundaryRoots(writer, rhs) and t = 1
    or
    not PointerTargetDomain::exprMayTargetTFromBoundaryRoots(writer, rhs) and t = 0
  ) and
  (
    PointerTargetDomain::exprMayTargetUFromBoundaryRoots(writer, rhs) and u = 1
    or
    not PointerTargetDomain::exprMayTargetUFromBoundaryRoots(writer, rhs) and u = 0
  ) and
  (
    PointerTargetDomain::exprMayTargetNullFromBoundaryRoots(writer, rhs) and n = 1
    or
    not PointerTargetDomain::exprMayTargetNullFromBoundaryRoots(writer, rhs) and n = 0
  )
select p.getFunction().getName() as function, p.getIndex() as binding_id, path as slot_path,
  calls as calls_below_interface, writer.getName() as writer_name,
  assign.getLocation().getFile().getRelativePath() as file,
  assign.getLocation().getStartLine() as line, concat(rhs.getAPrimaryQlClass(), ";") as rhs_class,
  calleeName(rhs) as rhs_callee, t as rule_t, u as rule_u, n as rule_null
