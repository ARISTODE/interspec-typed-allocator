import cpp

/**
 * P7c trusted-use inference for the PCRE1 name table used by the historical
 * nginx/libpcre InterSpec boundary.
 *
 * PCRE exposes the name table as an interior pointer into the compiled pcre
 * object. The security property is therefore not "this is an arbitrary byte
 * buffer"; T expects the returned range to remain inside a live compiled PCRE
 * allocation. The allocation itself uses PCRE's configurable pcre_malloc
 * function pointer, so P7c represents that allocator replacement explicitly as
 * a generated boundary helper site while retaining source-derived use policy.
 */

predicate trustedNameTableUse(string name, string typeName,
                              string functionName, int offset, int bytes) {
  exists(Function f, PointerType ownerType |
    f.getFile().getRelativePath() = "interspec_trusted_uses.c" and
    f.hasName("interspec_trusted_use_pcre_name_table") and
    f.getNumberOfParameters() = 3 and
    ownerType = f.getParameter(0).getType() and
    typeName = ownerType.getBaseType().getName() and
    name = "pcre_name_table_range" and
    functionName = f.getName() and
    offset = 0 and
    bytes = 0
  )
}

from string kind, string name, string typeName, string functionName,
     int offset, int bytes, int startLine, int startColumn, int endLine,
     int endColumn
where
  kind = "dynamic_use" and
  trustedNameTableUse(name, typeName, functionName, offset, bytes) and
  startLine = 0 and startColumn = 0 and endLine = 0 and endColumn = 0
select kind, name, typeName, functionName, offset, bytes,
       startLine, startColumn, endLine, endColumn
