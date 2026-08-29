# P7c Generalization Results

P7c validates the P7b `PolicyRuntime` and generated boundary-policy path on three additional real boundaries, while retaining rsync/popt as the baseline.

| Boundary | Allocation policy | Trusted uses | Helper sites | Pointer shape | Negative cases |
| --- | ---: | ---: | ---: | --- | --- |
| rsync/popt | 2 precise source-derived sites | 1 | 1 | returned string | wrong type, untracked |
| memcached/bipbuffer | 1 precise source-derived site | 1 | 1 | interior buffer + runtime extent | wrong type, untracked, out of bounds |
| nginx/libpcre | 0 direct-malloc sites | 1 | 2 | interior compiled-object name table | wrong type, untracked, out of bounds |
| yaml/libyaml | 0 direct-malloc sites | 1 | 2 | nested structured scalar output + runtime extent | wrong type, untracked, out of bounds |

The distinction between source-derived and helper sites is intentional. `bipbuf_new()` is a direct `malloc` selected by CodeQL and can use the precise P7a source-site path automatically. PCRE routes compiled-pattern allocation through its configurable `pcre_malloc` function pointer, and libyaml routes scalar allocation through `YAML_MALLOC`; those allocator abstractions are represented explicitly as generated boundary helper sites rather than being falsely reported as direct-malloc inference.

The final combined RLBox + NaCl test module runs the synthetic provenance attacks, isolated real rsync/popt attacks, memcached/bipbuffer, PCRE name-table, and libyaml scalar-output tests together. Each P7c boundary exercises a valid workload and rejects tracked wrong-type memory, untracked same-domain memory, and a valid pointer paired with an oversized runtime extent where applicable.

The generalization result is therefore about reuse of the Extended-SP3 security mechanism: generated type/use policy, generated site registration, `PolicyRuntime`, trusted allocation metadata, and type/liveness/spatial validation are shared. Application/library-specific API marshalling remains boundary-specific.

P7c does not prove intended-object identity among multiple simultaneously live allocations of the same trusted type. It also does not add general control-flow integrity or physical address reuse. Those remain outside the current security claim.
