#!/usr/bin/env python3

"""Module providing a Config class for managing Ash configuration settings"""

# pylint: disable=too-few-public-methods

import os
import sys
from urllib.parse import urlparse
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
    'verify_ssl',
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
            if not isinstance(config, list) or not config:
                print(f"Invalid config format in {self.config_file}. Expected a mapping or a non-empty list of mappings.")
                sys.exit(1)
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

        self._validate_config()
        self.config = config

    def _validate_config(self):
        if not getattr(self, 'base_url', None):
            print("Missing required config key: base_url")
            sys.exit(1)
        if not getattr(self, 'token', None):
            print("Missing required config key: token")
            sys.exit(1)

        parsed = urlparse(str(self.base_url))
        if parsed.scheme not in ('http', 'https') or not parsed.netloc:
            print(f"Invalid base_url: {self.base_url}. Expected an absolute URL with http/https.")
            sys.exit(1)

        if not getattr(self, 'api_path', None):
            self.api_path = '/api/controller/v2/'
        if not str(self.api_path).startswith('/'):
            print(f"Invalid api_path: {self.api_path}. It must start with '/'.")
            sys.exit(1)

        verify_ssl = getattr(self, 'verify_ssl', True)
        if isinstance(verify_ssl, str):
            verify_ssl = verify_ssl.strip().lower() in ('1', 'true', 'yes', 'y', 'on')
        self.verify_ssl = bool(verify_ssl)

    def __load_config(self):
        if os.path.exists(self.config_file):
            with open(self.config_file, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            if config is None:
                print(f"Configuration file {self.config_file} is empty.")
                sys.exit(1)
            return config

        print("You must create a config file " + str(self.config_file))
        print(CONFIG_EXAMPLE)
        sys.exit(1)
