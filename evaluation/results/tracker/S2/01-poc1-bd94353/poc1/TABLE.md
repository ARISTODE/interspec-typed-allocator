| Configuration | U reads help text | T's `val` after U's write | Pointer outside sandbox | Untracked pointer in sandbox | PoC 1, all three |
|---|---|---|---|---|---|
| rlbox_only | yes | 1337 | rejected (RLBox rejected outside-sandbox popt string) | completed | rejected (RLBox rejected outside-sandbox popt string) |
| switches_all_off | yes | 1337 | crashed (SIGSEGV) | completed | crashed (SIGSEGV) |
| domain_only_sp3 | no | 42 | rejected (InterSpec rejected popt char pointer: outside_domain) | completed | rejected (InterSpec rejected popt char pointer: outside_domain) |
| full_sp3 | no | 42 | rejected (InterSpec rejected popt char pointer: untracked) | rejected (InterSpec rejected popt char pointer: untracked) | rejected (InterSpec rejected popt char pointer: untracked) |
