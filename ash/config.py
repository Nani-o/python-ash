#!/usr/bin/env python3

"""Module providing a Config class for managing Ash configuration settings"""

# pylint: disable=too-few-public-methods

import os
import sys
from pathlib import Path

import yaml

CONFIG_EXAMPLE = """
example :
---
base_url: "https://your-aap-url.com"
token: "your-token"
api_path: "/api/controller/v2/"
...
"""

CONFIGS = [
    'base_url',
    'token',
    'api_path'
]

class Config():
    """Class for managing Ash configuration settings.
       Loads configuration from a YAML file and provides
       access to the settings as attributes."""

    def __init__(self):
        self.data_folder = Path.home().joinpath(".local", "share", "ash")
        config = self.__load_config()
        for k, v in config.items():
            if k in CONFIGS:
                setattr(self, k, v)
            else:
                print(f"Unknown config key: {k}")
                sys.exit(1)
        self.config = config

    def __load_config(self):
        if not self.data_folder.exists():
            self.data_folder.mkdir(parents=True, exist_ok=True)
        config_file = self.data_folder.joinpath('config.yml')
        if os.path.exists(config_file):
            with open(config_file, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            return config

        print("You must create a config file " + str(config_file))
        print(CONFIG_EXAMPLE)
        sys.exit(1)
