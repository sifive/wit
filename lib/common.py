#!/usr/bin/env python3

import logging
import sys

log = logging.getLogger('wit')


def error(*args, **kwargs):
    log.error(*args, **kwargs)
    sys.exit(1)
