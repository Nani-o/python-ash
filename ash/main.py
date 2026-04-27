#!/usr/bin/env python

"""
Application entry point
"""

from .ash import Ash
from .config import Config
from .cache import Cache
import argparse

def main():
    parser = argparse.ArgumentParser(prog='Ash', description='Ansible Shell for AAP')
    parser.add_argument('-c', 'config')
    args = parser.parse_args()
    
    config_file = args.config

    config = Config(config_file)
    cache = Cache()

    ash = Ash(config, cache)
    ash.run()

if __name__ == '__main__':
    main()
