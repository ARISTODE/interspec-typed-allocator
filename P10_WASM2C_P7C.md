# P10 wasm2c P7c Boundary Generalization

This branch extends the completed P9b RLBox wasm2c path from rsync/popt to the remaining P7c boundaries: memcached/bipbuffer, nginx/libpcre, and yaml/libyaml.

Completion requires each boundary to execute its valid path through RLBox wasm2c and to reject the adversarial cases already established by P7c where applicable: wrong trusted type, untracked same-domain pointer, spatial overflow, and stale pointer.

The implementation must reuse the P9b direct-import allocation-site provenance mechanism. Precise source-derived allocation sites and explicit boundary helper sites remain distinct in generated policy and reporting.
