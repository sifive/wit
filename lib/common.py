#!/usr/bin/env python3

import sys
from copy import deepcopy
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


# https://stackoverflow.com/a/845194
def passbyval(func):
    def new(self, *args):
        cargs = [deepcopy(arg) for arg in args]
        return func(self, *cargs)
    return new
