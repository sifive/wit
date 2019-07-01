#!/usr/bin/env python3

import sys

if sys.version_info[0] < 3 or sys.version_info[1] < 5:
    print("This program requires Python version 3.5 or newer")
    sys.exit(1)

if __name__ == '__main__':
    from .main import main
    main()
