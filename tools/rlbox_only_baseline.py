"""Environment of the RLBox-only variant in timing runs.

RLBox-only means the sandbox and a wrapper that enforces none of InterSpec's
policies: every field is copied to U and U's version of every field is copied
back. The wrapper builds read INTERSPEC_SP1 and INTERSPEC_SP2 and an unset
switch means on, so a tool that starts the RLBox-only binary without setting
them measures a wrapper with selective copying. The timing runs up to
2026-11-15 did that (EVAL_TRACKER.md, Log of 2026-11-15). Every timing tool
now starts the RLBox-only variant with this environment.
"""

import contextlib
import os

SWITCHES_OFF = {"INTERSPEC_SP1": "0", "INTERSPEC_SP2": "0"}
NAMES = ("rlbox-only", "rlbox_only")


def environment(variant, env):
    """A copy of env, with SP1 and SP2 off if variant is the RLBox-only one."""
    result = dict(env)
    if variant in NAMES:
        result.update(SWITCHES_OFF)
    return result


@contextlib.contextmanager
def process_environment(variant):
    """Set the switches in os.environ while a child of this variant is started."""
    saved = {name: os.environ.get(name) for name in SWITCHES_OFF}
    if variant in NAMES:
        os.environ.update(SWITCHES_OFF)
    try:
        yield
    finally:
        for name, value in saved.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value
