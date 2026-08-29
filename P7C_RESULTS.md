# P7c Generalization Results

P7c validates the P7b `PolicyRuntime` and generated boundary-policy path on three additional real library boundaries, while retaining rsync/popt as the baseline.

| Boundary | Source-derived allocation sites | Integration helper sites | Adversarial-only helper sites | Trusted uses | Use evidence | Pointer shape |
| --- | ---: | ---: | ---: | ---: | --- | --- |
| rsync/popt | 2 | 1 | 0 | 1 | real application source | returned string |
| memcached/bipbuffer | 1 | 0 | 1 | 1 | analysis adapter | interior buffer + runtime extent |
| nginx/libpcre | 0 | 1 | 1 | 1 | analysis adapter | interior compiled-object name table |
| yaml/libyaml | 0 | 1 | 1 | 1 | analysis adapter | nested structured scalar output + runtime extent |

The P8 accounting distinguishes integration policy from attack harness policy. The three adversarial-only helper sites above manufacture tracked memory of a different trusted type so the negative tests can exercise `wrong_type`; they are not required by a valid application integration and are excluded from integration-effort totals.

The distinction between source-derived and integration helper sites is also intentional. `poptGetContext`, `expandNextArg`, and `bipbuf_new()` expose supported direct-allocation patterns and are selected from source. PCRE routes compiled-pattern allocation through its configurable `pcre_malloc` function pointer, and libyaml routes scalar allocation through `YAML_MALLOC`; those allocator abstractions are represented explicitly as generated integration helper sites rather than being described as direct-malloc inference.

Trusted-use evidence has a separate provenance classification. The rsync/popt pointer use is derived from real `rsync/options.c`. The memcached, PCRE, and libyaml P7c uses are small T-side analysis adapters that represent the intended pointer-consumption shape for enforcement testing. They demonstrate that the mechanism handles those pointer shapes, but P7c/P8 do not claim those three uses were automatically inferred from the original applications' trusted source.

The final combined RLBox + NaCl test module runs the synthetic provenance attacks, isolated real rsync/popt attacks, memcached/bipbuffer, PCRE name-table, and libyaml scalar-output tests together. The real-boundary negative cases cover tracked wrong type, same-domain untracked pointer, and oversized runtime extent where applicable.

The generalization result is therefore about reuse of the Extended-SP3 security mechanism: generated type/use policy, generated site registration, `PolicyRuntime`, trusted allocation metadata, and type/liveness/spatial validation are shared. Application/library-specific API marshalling remains boundary-specific.

P7c does not prove intended-object identity among multiple simultaneously live allocations of the same trusted type. It also does not add general control-flow integrity or physical address reuse. Those remain outside the current security claim.
