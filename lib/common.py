#!/usr/bin/env python3

import sys
from lib.witlogger import getLogger

log = getLogger()


def error(*args, **kwargs):
    log.error(*args, **kwargs)
    sys.exit(1)


class WitUserError(Exception):
    """
    Supertype of user-input errors that should be reported without stack traces
    """
    pass
