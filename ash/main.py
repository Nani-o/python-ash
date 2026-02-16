#!/usr/bin/env python

"""
Application entry point
"""

from .ash import Ash
from .config import Config
from .cache import Cache

def main():
    config = Config()
    cache = Cache()

    ash = Ash(config.base_url, config.token, cache)
    ash.run()

if __name__ == '__main__':
    main()
