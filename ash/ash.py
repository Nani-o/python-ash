#!/usr/bin/env python

"""The Ash shell: REPL loop and initialization."""

from collections import OrderedDict
from os.path import expanduser

from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from prompt_toolkit.styles import Style

from .api import API
from .aap import AAP
from .commands import (
    ROOT_COMMANDS, CD_COMMANDS, LS_COMMANDS,
    LS_JOB_TEMPLATE_FILTERS, LS_JOBS_FILTERS,
    LS_PROJECTS_FILTERS, LS_INVENTORIES_FILTERS,
)
from .colors import COLORS
from .completer import AshCompleter, FormCompleter
from .display import DisplayMixin
from .context import ContextMixin
from .handlers import CommandHandlersMixin


class Ash(DisplayMixin, ContextMixin, CommandHandlersMixin):
    """The main Ash shell class.

    Initialises all state, then drives the interactive REPL.  All command
    handlers live in CommandHandlersMixin, display helpers in DisplayMixin,
    and context management in ContextMixin.
    """

    def __init__(self, config, cache):
        self.commands = ROOT_COMMANDS
        self.cd_commands = CD_COMMANDS
        self.ls_commands = LS_COMMANDS
        self.ls_commands_filters = {
            'job_templates': LS_JOB_TEMPLATE_FILTERS,
            'jobs': LS_JOBS_FILTERS,
            'projects': LS_PROJECTS_FILTERS,
            'inventories': LS_INVENTORIES_FILTERS,
        }

        if getattr(config, 'api_path', None):
            api_path = config.api_path
        else:
            api_path = "/api/controller/v2/"
        self.api = API(config.base_url, config.token, api_path)
        self.api_description = getattr(config, 'description', None)
        self.api_description_color = getattr(config, 'description_color', 'white')
        self.aap = AAP(self.api)
        self.cache = cache
        self._load_all_caches()

        self.current_context = None
        self.current_context_type = None
        self.last_context = None
        self.last_context_type = None
        self.form = None

        self.colors = COLORS
        self.style = Style.from_dict(self.colors)

        history_file_path = expanduser("~/.ash_history")
        self.history = FileHistory(history_file_path)
        self.completer = AshCompleter(self)
        self.form_completer = FormCompleter(self)
        self.session = PromptSession(history=self.history, style=self.style)
        self.session_wo_history = PromptSession(style=self.style)

        # Build a flat dispatch table for all known commands so the REPL
        # never uses fragile getattr name-mangling.
        self._command_dispatch = {
            'ls': self._cmd_ls,
            'cd': self._cmd_cd,
            'watch': self._cmd_watch,
            'cache': self._cmd_cache,
            'refresh': self._cmd_refresh,
            'url': self._cmd_url,
            'open': self._cmd_open,
            'info': self._cmd_info,
            'jobs': self._cmd_jobs,
            'launch': self._cmd_launch,
            'sync': self._cmd_sync,
            'template': self._cmd_template,
            'project': self._cmd_project,
            'inventory': self._cmd_inventory,
            'hosts': self._cmd_hosts,
            'add_hosts': self._cmd_add_hosts,
            'clear_hosts': self._cmd_clear_hosts,
            'relaunch': self._cmd_relaunch,
            'cancel': self._cmd_cancel,
            'output': self._cmd_output,
            'reuse': self._cmd_reuse,
        }

    def filter_objects(self, objects, args, filter_definitions):
        if args:
            for arg in [a.lower() for a in args]:
                filter = [f for f in filter_definitions.keys() if arg.startswith(f + ':')]
                if filter:
                    filter_key = filter[0]
                    filter_value = arg.split(':', 1)[1].strip()
                    if not filter_value:
                        self.print(
                            f"Invalid filter format: '{arg}'. Expected format is 'filter:value'.",
                            'red'
                        )
                        return []
                    objects = [
                        obj for obj in objects
                        if filter_value.lower()
                        in obj.data["summary_fields"].get(filter_key, {}).get('name', '').lower()
                        or filter_value.lower()
                        in obj.data["summary_fields"].get(filter_key, {}).get('username', '').lower()
                        or filter_value.lower() in str(obj.data.get(filter_key, '')).lower()
                    ]
                else:
                    objects = [obj for obj in objects if arg in obj.name.lower()]
        return objects

    def _get_objects(self, object_type):
        objects = self.cache.load_cache(object_type)
        if objects:
            print(f"Loaded {object_type} from cache, use 'cache' command to refresh.")
        else:
            print(f"Retrieving and caching {object_type}")
            method = getattr(self.aap, f'get_{object_type}')
            objects = method()
            if not objects:
                return [], {}, {}
            for obj in objects:
                self.cache.insert_cache(object_type, obj.id, obj)
            print(f"{len(objects)} {object_type} cached.")

        objects_by_id = {obj.id: obj for obj in objects}
        objects_by_name = {obj.name: obj for obj in objects}
        return objects, objects_by_id, objects_by_name

    def _load_inventories_cache(self):
        self.inventories, self.inventories_by_id, self.inventories_by_name = (
            self._get_objects('inventories')
        )

    def _load_job_templates_cache(self):
        self.job_templates, self.job_templates_by_id, self.job_templates_by_name = (
            self._get_objects('job_templates')
        )

    def _load_projects_cache(self):
        self.projects, self.projects_by_id, self.projects_by_name = (
            self._get_objects('projects')
        )

    def _load_all_caches(self):
        self._load_inventories_cache()
        self._load_job_templates_cache()
        self._load_projects_cache()

    def run(self):
        while True:
            try:
                text = self.session.prompt(
                    self.get_prompt(), completer=self.completer, multiline=False
                )
            except KeyboardInterrupt:
                continue
            except EOFError:
                break

            arr = text.strip().split(' ')
            command, args = arr[0], arr[1:]

            if command == 'exit':
                break
            if command == '':
                continue
            if command in self.commands:
                handler = self._command_dispatch.get(command)
                if handler:
                    try:
                        handler(args)
                    except KeyboardInterrupt:
                        self.print("\nCommand interrupted by user.", 'red')
                else:
                    print(f'Command not implemented: {command}')
            else:
                print(f'Unknown command: {command}')

        print('[ash is terminating]')
