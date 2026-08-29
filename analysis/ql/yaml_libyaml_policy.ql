import cpp

/**
 * P7c trusted-use inference for libyaml structured event output.
 *
 * yaml_scalar_event_initialize() stores a heap-owned scalar pointer and length
 * inside yaml_event_t::data.scalar. The CodeQL-only trusted-use adapter models
 * T consuming that nested pointer/extent. The scalar allocation itself goes
 * through libyaml's YAML_MALLOC abstraction, so the selected event allocation
 * is represented honestly as an explicit generated boundary helper site.
 */

predicate trustedScalarEventUse(string name, string typeName,
                                string functionName, int offset, int bytes) {
  exists(Function f |
    f.getFile().getRelativePath() = "interspec_trusted_uses.c" and
    f.hasName("interspec_trusted_use_yaml_scalar") and
    f.getNumberOfParameters() = 1 and
    name = "yaml_scalar_value_range" and
    typeName = "yaml_scalar_value" and
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
  trustedScalarEventUse(name, typeName, functionName, offset, bytes) and
  startLine = 0 and startColumn = 0 and endLine = 0 and endColumn = 0
select kind, name, typeName, functionName, offset, bytes,
       startLine, startColumn, endLine, endColumn
