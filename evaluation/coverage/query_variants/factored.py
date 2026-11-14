"""Variant `paper_counting_rule_factored` (tracker item C2): new text of seven
predicates of ql/lib/PointerTargetDomain.qll.

The shipped predicates have the form P(Function f, Expr expr) with disjuncts
that do not mention f. Such a disjunct holds for every function of the
database, so the relation has (functions in the database) x (expressions)
rows: 2.4 billion on ffmpeg/libvpx, and the evaluation does not finish.

Each predicate is written here as

    P(f, expr)  :=  PAnyFunction(expr)  or  PForFunction(f, expr)

where PAnyFunction holds the disjuncts without f and PForFunction the
disjuncts that bind f. P itself becomes an inlined predicate with f bound by
the caller (every caller binds f), so the product is never built. The
disjuncts are the shipped ones, moved, not changed.

One disjunct needs care: exprContainsAddressOfNonBoundaryRoots(f, expr) holds
for an address-of expression unless f has a T-to-U boundary parameter from
which the operand derives. It is split by whether any function excludes the
address: if none does, the disjunct holds for every f (PAnyFunction); if some
do, it holds for every f that does not (c2UAddressExcludedElsewhere).

Keys: predicate name. Values: (SHA-256 of the shipped block, new text). A
block is the text from the line `  predicate NAME(` to the next line `  }`.
"""

U_DIRECT = '''  // C2 variant paper_counting_rule_factored. Shipped body:
  //   exprContainsMallocLikeCall(expr) or exprContainsIndirectAllocatorCall(expr)
  //   or exprDerivedFromUntrustedInputPointer(f, expr)
  //   or exprContainsAddressOfNonBoundaryRoots(f, expr)
  //   or exprContainsUntrustedGlobalPointerVar(expr)
  //   or exprContainsArrayVariableFromUntrusted(expr)
  //   or exprContainsUntrustedStringLiteral(expr)
  //   or (expr contains an access of local v and localVarMayTargetUDirectFromBoundaryRoots(f, v))
  predicate c2UntrustedAddressOf(AddressOfExpr addr) {
    exists(Variable base |
      primaryPointerBaseVarLValue(addr.getOperand(), base) and
      (
        PointerBoundaryBase::isUntrustedFile(base.getFile())
        or exprOccursInUntrustedCode(addr)
      )
    )
  }

  predicate c2AddressExcludedFor(Function f, AddressOfExpr addr) {
    exists(PointerBoundaryBase::BoundaryParameter bp |
      bp.getFunction() = f and bp.direction("T_TO_U") and
      lvalueDerivedFromParameterValue(bp, addr.getOperand())
    )
  }

  predicate c2ContainsUntrustedAddressNeverExcluded(Expr expr) {
    exists(AddressOfExpr addr |
      PointerBoundaryBase::exprContains(expr, addr) and
      c2UntrustedAddressOf(addr) and
      not c2AddressExcludedFor(_, addr)
    )
  }

  predicate c2ContainsUntrustedAddressSometimesExcluded(Expr expr, AddressOfExpr addr) {
    PointerBoundaryBase::exprContains(expr, addr) and
    c2UntrustedAddressOf(addr) and
    c2AddressExcludedFor(_, addr)
  }

  bindingset[f]
  pragma[inline]
  predicate c2UAddressExcludedElsewhere(Function f, Expr expr) {
    exists(AddressOfExpr addr |
      c2ContainsUntrustedAddressSometimesExcluded(expr, addr) and
      not c2AddressExcludedFor(f, addr)
    )
  }

  predicate c2UDirectAnyFunction(Expr expr) {
    exprContainsMallocLikeCall(expr)
    or exprContainsIndirectAllocatorCall(expr)
    or c2ContainsUntrustedAddressNeverExcluded(expr)
    or exprContainsUntrustedGlobalPointerVar(expr)
    or exprContainsArrayVariableFromUntrusted(expr)
    or exprContainsUntrustedStringLiteral(expr)
  }

  predicate c2UDirectForFunction(Function f, Expr expr) {
    exprDerivedFromUntrustedInputPointer(f, expr)
    or exists(VariableAccess va, LocalVariable v |
      PointerBoundaryBase::exprContains(expr, va) and
      v = va.getTarget() and
      localVarMayTargetUDirectFromBoundaryRoots(f, v)
    )
  }

  bindingset[f]
  pragma[inline]
  predicate exprMayTargetUDirectFromBoundaryRoots(Function f, Expr expr) {
    c2UDirectAnyFunction(expr)
    or c2UDirectForFunction(f, expr)
    or c2UAddressExcludedElsewhere(f, expr)
  }
'''

U_SEED = '''  // C2 variant paper_counting_rule_factored. Shipped body:
  //   exprMayTargetUDirectFromBoundaryRoots(f, expr)
  //   or (expr contains a pointer-typed call of a callee with functionMayReturnUDirect)
  predicate c2USeedAnyFunction(Expr expr) {
    c2UDirectAnyFunction(expr)
    or exists(FunctionCall call, Function callee, PointerType pt |
      PointerBoundaryBase::exprContains(expr, call) and
      call.getTarget() = callee and
      PointerSlotUnified::pointerType(call.getUnspecifiedType(), pt) and
      functionMayReturnUDirect(callee)
    )
  }

  bindingset[f]
  pragma[inline]
  predicate exprMayTargetUSeed(Function f, Expr expr) {
    c2USeedAnyFunction(expr)
    or c2UDirectForFunction(f, expr)
    or c2UAddressExcludedElsewhere(f, expr)
  }
'''

U_FULL = '''  // C2 variant paper_counting_rule_factored. The shipped disjuncts, in the
  // shipped order: direct; call of a callee that may return U; call of a
  // boundary return that may target U; access of a local that may target U
  // (the only one that binds f besides the direct part); load from a container;
  // load from a field.
  predicate c2UFullAnyFunction(Expr expr) {
    c2UDirectAnyFunction(expr)
    or exists(FunctionCall call, Function callee, PointerType pt |
      PointerBoundaryBase::exprContains(expr, call) and
      call.getTarget() = callee and
      PointerSlotUnified::pointerType(call.getUnspecifiedType(), pt) and
      (functionMayReturnUDirect(callee) or functionMayReturnUNonCall(callee))
    )
    // Propagate target-domain summaries through calls to other boundary-return
    // APIs. This captures thin wrappers like `foo() { return bar(); }` where
    // `bar` is itself a boundary return whose return expression is non-trivial
    // (for example, defined via helper out-parameters).
    or exists(FunctionCall call, PointerBoundaryBase::BoundaryReturn r, PointerType pt |
      PointerBoundaryBase::exprContains(expr, call) and
      call.getTarget() = r and
      PointerSlotUnified::pointerType(call.getUnspecifiedType(), pt) and
      returnMayTargetU(r)
    )
    or exists(Variable container |
      exprLoadsPointerFromContainerSubobject(expr, container) and
      not exists(Field fld | exprLoadsPointerFromField(expr, fld)) and
      containerMayHoldUntrustedPointersForBoundaryReturn(container)
    )
    or exists(Field fld |
      exprLoadsPointerFromField(expr, fld) and
      fieldMayHoldUntrustedPointersForBoundaryReturn(fld)
    )
  }

  predicate c2UFullForFunction(Function f, Expr expr) {
    c2UDirectForFunction(f, expr)
    or exists(VariableAccess va, LocalVariable v |
      PointerBoundaryBase::exprContains(expr, va) and
      v = va.getTarget() and
      localVarMayTargetUFromBoundaryRoots(f, v)
    )
  }

  bindingset[f]
  pragma[inline]
  predicate exprMayTargetUFromBoundaryRoots(Function f, Expr expr) {
    c2UFullAnyFunction(expr)
    or c2UFullForFunction(f, expr)
    or c2UAddressExcludedElsewhere(f, expr)
  }
'''

T_DIRECT = '''  // C2 variant paper_counting_rule_factored. Shipped body: four disjuncts
  // without f, then the access of a local with
  // localVarMayTargetTDirectFromTrustedRoots(f, v).
  predicate c2TDirectAnyFunction(Expr expr) {
    exprContainsMallocLikeCallInTrusted(expr)
    or exprContainsAddressOfTrustedVar(expr)
    or exprContainsArrayVariableFromTrusted(expr)
    or exprContainsTrustedStringLiteral(expr)
  }

  predicate c2TDirectForFunction(Function f, Expr expr) {
    exists(VariableAccess va, LocalVariable v |
      PointerBoundaryBase::exprContains(expr, va) and
      v = va.getTarget() and
      localVarMayTargetTDirectFromTrustedRoots(f, v)
    )
  }

  bindingset[f]
  pragma[inline]
  predicate exprMayTargetTDirectFromTrustedRoots(Function f, Expr expr) {
    c2TDirectAnyFunction(expr)
    or c2TDirectForFunction(f, expr)
  }
'''

T_SEED = '''  // C2 variant paper_counting_rule_factored. Shipped body:
  //   (not G(expr) and (exprDerivedFromTrustedInputPointer(f, expr) or A or B or C))
  //   or (expr contains a pointer-typed call of a callee with functionMayReturnTDirect)
  // with G = "the normalized expr is a call of a callee that may return U
  // directly and not T directly". Only the first of the four inner disjuncts
  // mentions f.
  pragma[inline]
  predicate c2TSeedGuard(Expr expr) {
    not exists(Expr norm, FunctionCall topCall, Function callee, PointerType pt |
      normalizeExpr(expr, norm) and
      topCall = norm and
      topCall.getTarget() = callee and
      PointerSlotUnified::pointerType(topCall.getUnspecifiedType(), pt) and
      functionMayReturnUDirect(callee) and
      not functionMayReturnTDirect(callee)
    )
  }

  predicate c2TSeedAnyFunction(Expr expr) {
    (
      c2TSeedGuard(expr) and
      (
        exprContainsArrayVariableFromTrusted(expr)
        or exprContainsAddressOfTrustedVar(expr)
        or exprContainsTrustedStringLiteral(expr)
      )
    )
    or exists(FunctionCall call, Function callee, PointerType pt |
      PointerBoundaryBase::exprContains(expr, call) and
      call.getTarget() = callee and
      PointerSlotUnified::pointerType(call.getUnspecifiedType(), pt) and
      functionMayReturnTDirect(callee)
    )
  }

  predicate c2TSeedForFunction(Function f, Expr expr) {
    exprDerivedFromTrustedInputPointer(f, expr) and
    c2TSeedGuard(expr)
  }

  bindingset[f]
  pragma[inline]
  predicate exprMayTargetTSeed(Function f, Expr expr) {
    c2TSeedAnyFunction(expr)
    or c2TSeedForFunction(f, expr)
  }
'''

T_FULL = '''  // C2 variant paper_counting_rule_factored. The shipped disjuncts. Those that
  // mention f: exprDerivedFromTrustedInputPointer(f, expr) under the guard
  // "not exprLoadsPointerFromBoundaryReturnStorage(expr)"; the access of a
  // local with localVarMayTargetTFromBoundaryRoots(f, v); the call of a callee
  // that returns a pointer derived from parameter i, with
  // exprDerivedFromTrustedInputPointer(f, argument i).
  predicate c2TFullAnyFunction(Expr expr) {
    (
      not exprLoadsPointerFromBoundaryReturnStorage(expr) and
      (
        exprContainsArrayVariableFromTrusted(expr)
        or exprContainsIndirectAllocatorCallToTrusted(expr)
        or exprContainsTrustedStringLiteral(expr)
      )
    )
    or exists(FunctionCall call, Function callee, PointerType pt |
      PointerBoundaryBase::exprContains(expr, call) and
      call.getTarget() = callee and
      PointerSlotUnified::pointerType(call.getUnspecifiedType(), pt) and
      (functionMayReturnTDirect(callee) or functionMayReturnTNonCall(callee))
    )
    or exists(FunctionCall call, PointerBoundaryBase::BoundaryReturn r, PointerType pt |
      PointerBoundaryBase::exprContains(expr, call) and
      call.getTarget() = r and
      PointerSlotUnified::pointerType(call.getUnspecifiedType(), pt) and
      returnMayTargetT(r)
    )
    or exists(Variable container |
      exprLoadsPointerFromContainerSubobject(expr, container) and
      not exists(Field fld | exprLoadsPointerFromField(expr, fld)) and
      containerMayHoldTrustedPointersForBoundaryReturn(container)
    )
    or exists(Field fld |
      exprLoadsPointerFromField(expr, fld) and
      fieldMayHoldTrustedPointersForBoundaryReturn(fld)
    )
  }

  predicate c2TFullForFunction(Function f, Expr expr) {
    (
      not exprLoadsPointerFromBoundaryReturnStorage(expr) and
      exprDerivedFromTrustedInputPointer(f, expr)
    )
    or exists(VariableAccess va, LocalVariable v |
      PointerBoundaryBase::exprContains(expr, va) and
      v = va.getTarget() and
      localVarMayTargetTFromBoundaryRoots(f, v)
    )
    or exists(FunctionCall call, Function callee, int i |
      PointerBoundaryBase::exprContains(expr, call) and
      call.getTarget() = callee and
      functionReturnsPointerDerivedFromParam(callee, i) and
      exprDerivedFromTrustedInputPointer(f, call.getArgument(i))
    )
  }

  bindingset[f]
  pragma[inline]
  predicate exprMayTargetTFromBoundaryRoots(Function f, Expr expr) {
    c2TFullAnyFunction(expr)
    or c2TFullForFunction(f, expr)
  }
'''

NULL_FULL = '''  // C2 variant paper_counting_rule_factored. The shipped disjuncts; only the
  // second (the normalized expr is an access of a local with
  // localVarMayTargetNullFromBoundaryRoots(f, v)) mentions f.
  predicate c2NullAnyFunction(Expr expr) {
    exprContainsNullPointerLiteral(expr)
    or exists(FunctionCall call, Function callee, PointerType pt |
      PointerBoundaryBase::exprContains(expr, call) and
      call.getTarget() = callee and
      PointerSlotUnified::pointerType(call.getUnspecifiedType(), pt) and
      functionMayReturnNull(callee)
    )
    or exists(Variable container |
      exprLoadsPointerFromContainerSubobject(expr, container) and
      not exists(Field fld | exprLoadsPointerFromField(expr, fld)) and
      containerMayHoldNullPointersForBoundaryReturn(container)
    )
    or exists(Field fld |
      exprLoadsPointerFromField(expr, fld) and
      fieldMayHoldNullPointersForBoundaryReturn(fld)
    )
  }

  predicate c2NullForFunction(Function f, Expr expr) {
    exists(Expr norm, VariableAccess va, LocalVariable v |
      normalizeExpr(expr, norm) and
      va = norm and
      v = va.getTarget() and
      localVarMayTargetNullFromBoundaryRoots(f, v)
    )
  }

  bindingset[f]
  pragma[inline]
  predicate exprMayTargetNullFromBoundaryRoots(Function f, Expr expr) {
    c2NullAnyFunction(expr)
    or c2NullForFunction(f, expr)
  }
'''

PREDICATES = {
    "exprMayTargetUDirectFromBoundaryRoots": ("06aeef434fb75dfd917c183733d29393c7b02aca377e35dbdfe2ee2714ae595c", U_DIRECT),
    "exprMayTargetUSeed": ("5cb7463cb211246994e8113f738d880161dbb9d401896c4ba74434a6847f8a6f", U_SEED),
    "exprMayTargetUFromBoundaryRoots": ("1679a2e1817a0ac6e69ec66829c1b40e5a51144161f22154d6d3935b468dc275", U_FULL),
    "exprMayTargetTDirectFromTrustedRoots": ("c7a16ee40897a39d993431051ff20ea65573a5fc6ab553da4ce61c171006fd35", T_DIRECT),
    "exprMayTargetTSeed": ("efb8b4f228b5e5b54c64c62815d60494938826adb175e56ce2f5ad92d71ab82b", T_SEED),
    "exprMayTargetTFromBoundaryRoots": ("e3a33b5ff8543a7686f5f4f21a48279b7ec127f0d75d7270c2783495ad10ffa8", T_FULL),
    "exprMayTargetNullFromBoundaryRoots": ("21f79dca6ead267e9a1150235a856dc28b8107efb38e94cbc3c220bca2d1dfb6", NULL_FULL),
}
