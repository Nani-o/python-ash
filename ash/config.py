#!/usr/bin/env python3

"""Module providing a Config class for managing Ash configuration settings"""

# pylint: disable=too-few-public-methods

import os
import sys
from pathlib import Path
from iterfzf import iterfzf

import yaml

CONFIG_EXAMPLE = """
Simple configuration example:
---
base_url: "https://your-aap-url.com"
token: "your-token"
api_path: "/api/controller/v2/"
...

Or multiple configurations:
---
- base_url: "https://your-aap-url.com
  token: "your-token"
  api_path: "/api/controller/v2/"
  description: "My AAP instance"
  description_color: "green"
- base_url: "https://your-other-aap-url.com"
  token: "your-other-token"
  api_path: "/api/controller/v2/"
  description: "My other AAP instance"
"""

CONFIGS = [
    'base_url',
    'token',
    'api_path',
    'description',
    'description_color'
]

class Config():
    """Class for managing Ash configuration settings.
       Loads configuration from a YAML file and provides
       access to the settings as attributes."""

    def __init__(self, config_file=None):
        if not config_file:
            self.data_folder = Path.home().joinpath(".local", "share", "ash")
            if not self.data_folder.exists():
                self.data_folder.mkdir(parents=True, exist_ok=True)
            self.config_file = self.data_folder.joinpath('config.yml')
        else:
            self.config_file = config_file
        config = self.__load_config()
        if not isinstance(config, dict):
            if len(config) == 1:
                config = config[0]
            else:
                choices = []
                for idx, item in enumerate(config):
                    description = item.get('description', 'No description provided')
                    base_url = item.get('base_url', 'No base_url provided')
                    choices.append(f"{idx + 1}. {base_url} - {description}")

                options = {"--layout=reverse"}
                height = len(choices) + 2
                user_input = None
                options.add(f"--height={height}")
                while not user_input:
                    user_input = iterfzf(choices, prompt="Multiple configurations found in the config file. Please select one:", __extra__=options)
                idx = int(user_input.split('.')[0]) - 1
                config = config[idx]

        for k, v in config.items():
            if k in CONFIGS:
                setattr(self, k, v)
            else:
                print(f"Unknown config key: {k}")
                sys.exit(1)
        self.config = config

    def __load_config(self):
        if os.path.exists(self.config_file):
            with open(self.config_file, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            return config

        print("You must create a config file " + str(self.config_file))
        print(CONFIG_EXAMPLE)
        sys.exit(1)
