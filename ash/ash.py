#!/usr/bin/env python

from collections import OrderedDict
from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from prompt_toolkit.styles import Style
from os.path import expanduser

from .aap import AAP, API
from .models import Inventory, JobTemplate, Project, Job
from .display import Display
from .completer import AshCompleter, FormCompleter
from .commands import ROOT_COMMANDS, CD_COMMANDS, LS_COMMANDS, LS_JOB_TEMPLATE_FILTERS, LS_JOBS_FILTERS, LS_PROJECTS_FILTERS, LS_INVENTORIES_FILTERS, JT_COMMANDS, JOB_COMMANDS, INVENTORY_COMMANDS, PROJECT_COMMANDS
from .colors import COLORS
from .handlers.base import BaseHandler
from .handlers.root import RootHandler
from .handlers.job_template import JobTemplateHandler
from .handlers.job import JobHandler
from .handlers.inventory import InventoryHandler
from .handlers.project import ProjectHandler

class Ash(object):
    def __init__(self, config, cache):
        self.commands = ROOT_COMMANDS
        self.cd_commands = CD_COMMANDS
        self.ls_commands = LS_COMMANDS
        self.ls_commands_filters = {
            'job_templates': LS_JOB_TEMPLATE_FILTERS,
            'jobs': LS_JOBS_FILTERS,
            'projects': LS_PROJECTS_FILTERS,
            'inventories': LS_INVENTORIES_FILTERS
        }
        self.job_template_commands = JT_COMMANDS
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
        self.colors = COLORS
        history_file_path = expanduser("~/.ash_history")
        self.history = FileHistory(history_file_path)
        self.completer = AshCompleter(self)
        self.form_completer = FormCompleter(self)
        self.style = Style.from_dict(self.colors)
        self.display = Display(self.style)
        self.session = PromptSession(history=self.history, style=self.style)
        self.session_wo_history = PromptSession(style=self.style)
        self._base_handler = BaseHandler(self)
        self._root_handler = RootHandler(self)
        self._jt_handler = JobTemplateHandler(self)
        self._job_handler = JobHandler(self)
        self._inventory_handler = InventoryHandler(self)
        self._project_handler = ProjectHandler(self)
        self._command_handlers = self._build_command_handlers()

    def _build_command_handlers(self):
        """Return explicit command-to-method mapping used by the command loop."""
        return {
            'ls': self._root_handler.ls,
            'watch': self._root_handler.watch,
            'cd': self._root_handler.cd,
            'cache': self._root_handler.cache,
            'refresh': self._base_handler.refresh,
            'url': self._base_handler.url,
            'open': self._base_handler.open,
            'info': self._base_handler.info,
            'launch': self._jt_handler.launch,
            'jobs': self._jt_handler.jobs,
            'relaunch': self._job_handler.relaunch,
            'reuse': self._job_handler.reuse,
            'cancel': self._job_handler.cancel,
            'output': self._job_handler.output,
            'template': self._job_handler.template,
            'hosts': self._inventory_handler.hosts,
            'add_hosts': self._inventory_handler.add_hosts,
            'clear_hosts': self._inventory_handler.clear_hosts,
            'sync': self._base_handler.sync,
            'project': self._base_handler.project,
            'inventory': self._base_handler.inventory,
        }

    def _get_objects(self, object_type):
        objects = self.cache.load_cache(object_type)
        if objects:
            print(f"Loaded {object_type} from cache, use 'cache' command to refresh.")
        else:
            print(f"Retrieving and caching {object_type}")
            method = getattr(self.aap, f'get_{object_type}')
            objects = method()
            if not objects:
                return [], [], []
            for obj in objects:
                self.cache.insert_cache(object_type, obj.id, obj)
            print(f"{len(objects)} {object_type} cached.")

        objects_by_id = {obj.id: obj for obj in objects}
        objects_by_name = {obj.name: obj for obj in objects}

        return objects, objects_by_id, objects_by_name

    def _load_inventories_cache(self):
        self.inventories, self.inventories_by_id, self.inventories_by_name = self._get_objects('inventories')

    def _load_job_templates_cache(self):
        self.job_templates, self.job_templates_by_id, self.job_templates_by_name = self._get_objects('job_templates')

    def _load_projects_cache(self):
        self.projects, self.projects_by_id, self.projects_by_name = self._get_objects('projects')

    def _load_all_caches(self):
        self._load_inventories_cache()
        self._load_job_templates_cache()
        self._load_projects_cache()

    def filter_objects(self, objects, args, filter_definitions):
        if args:
            for arg in [a.lower() for a in args]:
                filter = [filter for filter in filter_definitions.keys() if arg.startswith(filter + ':')]
                if filter:
                    filter_key = filter[0]
                    filter_value = arg.split(':', 1)[1].strip()
                    if not filter_value:
                        self.display.print(f"Invalid filter format: '{arg}'. Expected format is 'filter:value'.", 'red')
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

    # ------------------------------------------------------------------ #
    # Context switching helpers (called by handlers)
    # ------------------------------------------------------------------ #

    def _get_commands_for_context(self, context_type):
        if context_type == 'job_templates':
            return OrderedDict(list(JT_COMMANDS.items()) + list(ROOT_COMMANDS.items()))
        elif context_type == 'jobs':
            return OrderedDict(list(JOB_COMMANDS.items()) + list(ROOT_COMMANDS.items()))
        elif context_type == 'inventories':
            return OrderedDict(list(INVENTORY_COMMANDS.items()) + list(ROOT_COMMANDS.items()))
        elif context_type == 'projects':
            return OrderedDict(list(PROJECT_COMMANDS.items()) + list(ROOT_COMMANDS.items()))
        else:
            return ROOT_COMMANDS.copy()

    def _switch_context(self, context, context_type):
        self.last_context = self.current_context
        self.last_context_type = self.current_context_type
        self.current_context = context
        self.current_context_type = context_type
        if self.current_context is not None:
            if self.current_context_type != 'jobs':
                self.current_context.refresh()
                self.cache.insert_cache(self.current_context_type, self.current_context.id, self.current_context)
            if context_type == 'job_templates':
                self.display.print(f"Switched context to Job Template: ID={context.id}, Name={context.name}", 'cyan')
            elif context_type == 'jobs':
                self.display.print(f"Switched context to Job: ID={context.id}, Name={context.name}", self.display.status_to_color(context.status))
            elif context_type == 'inventories':
                self.display.print(f"Switched context to Inventory: ID={context.id}, Name={context.name}", 'green')
            elif context_type == 'projects':
                self.display.print(f"Switched context to Project: ID={context.id}, Name={context.name}", 'orange')
        else:
            self.display.print("Switched to root context", 'white')

        self.commands = self._get_commands_for_context(context_type)

    def _find_matching_objects(self, objects, identifier):
        matches = [obj for obj in objects if identifier.lower() in obj.name.lower()]
        exact_matches = [obj for obj in matches if identifier.lower() == obj.name.lower()]
        if len(exact_matches) == 1:
            return exact_matches[0]
        elif len(matches) == 1:
            return matches[0]
        elif len(matches) > 1:
            user_input = self._base_handler._multiple_choice_prompt("Multiple matches found", f"Multiple objects found matching '{identifier}'. Please select one:", [f"{obj.id}: {obj.name}" for obj in matches], required=True)
            if user_input:
                selected_id = int(user_input.split(':', 1)[0])
                return next((obj for obj in matches if obj.id == selected_id), None)
        return None

    # Change directory command implementations
    #
    # Note: The CD commands will attempt to find the specified object by ID first, then by name (case-insensitive, partial match).
    # If multiple matches are found by name, it will list the matches and ask the user to refine their input.
    # The context is switched to the specified object and the available commands are updated accordingly.

    def _cd_job_template(self, args):
        identifier = ' '.join(args)
        jt = None
        if identifier.isdigit():
            jt = self.job_templates_by_id.get(int(identifier))
        else:
            jt = self._find_matching_objects(self.job_templates, identifier)

        if not jt:
            self.display.print(f"Job Template '{identifier}' not found.", 'red')
            return
        self._switch_context(jt, 'job_templates')

    def _cd_job(self, args):
        identifier = ' '.join(args)
        job = None
        if identifier.isdigit():
            job = self.aap.get_job(int(identifier))
        else:
            jobs = list(reversed(self.aap.get_jobs(filters={'search': identifier}, result_limit=100)))
            if jobs:
                jobs_list = ["{}: {} - {:<15} {} {}".format(job.id, job.name, self.display.parse_label(job.limit, 15), job.status, self.display.parse_label(job.created)) for job in jobs]
                job = self._base_handler._multiple_choice_prompt("Job", f"Multiple jobs found matching '{identifier}'. Please select one:", jobs_list, required=True)
                if job:
                    job_id = int(job.split(':', 1)[0])
                    job = next((j for j in jobs if j.id == job_id), None)
        if not job:
            self.display.print(f"Job '{identifier}' not found.", 'red')
            return
        self._switch_context(job, 'jobs')

    def _cd_inventory(self, args):
        identifier = ' '.join(args)
        inv = None
        if identifier.isdigit():
            inv = self.inventories_by_id.get(int(identifier))
        else:
            inv = self._find_matching_objects(self.inventories, identifier)

        if not inv:
            self.display.print(f"Inventory '{identifier}' not found.", 'red')
            return
        self._switch_context(inv, 'inventories')

    def _cd_project(self, args):
        identifier = ' '.join(args)
        proj = None
        if identifier.isdigit():
            proj = self.projects_by_id.get(int(identifier))
        else:
            proj = self._find_matching_objects(self.projects, identifier)

        if not proj:
            self.display.print(f"Project '{identifier}' not found.", 'red')
            return
        self._switch_context(proj, 'projects')

    # Delegation aliases used by handlers/tests via the Ash surface.

    def _ask_variable(self, var):
        """Delegate to the base handler. Public alias so handlers and tests can reference it on Ash."""
        return self._base_handler._ask_variable(var)

    def _cmd_output(self, args):
        """Alias so handlers can call ash._cmd_output([]) without name-mangling."""
        self._job_handler.output(args)

    def get_prompt(self):
        prompt = []
        prompt.append(('class:white', 'ash '))
        if self.api_description:
            prompt.append((f'class:{self.api_description_color}', f'[{self.api_description}] '))
        if self.current_context:
            if isinstance(self.current_context, JobTemplate):
                prompt.append(('class:cyan', f'JobTemplate[{self.current_context.id}] - {self.current_context.name} '))
            elif isinstance(self.current_context, Inventory):
                prompt.append(('class:green', f'Inventory[{self.current_context.id}] - {self.current_context.name} '))
            elif isinstance(self.current_context, Project):
                prompt.append(('class:orange', f'Project[{self.current_context.id}] - {self.current_context.name} '))
            elif isinstance(self.current_context, Job):
                color = self.display.status_to_color(self.current_context.status)
                prompt.append((f'class:{color}', f'Job[{self.current_context.id}] - {self.current_context.name} - {self.current_context.status} '))

        prompt.append(('class:white', '> '))
        return prompt

    def run(self):
        while True:
            try:
                text = self.session.prompt(self.get_prompt(), completer=self.completer, multiline=False)
                # text = self.session.prompt(self.get_prompt(), refresh_interval=0.5, reserve_space_for_menu=0)
            except KeyboardInterrupt:
                continue  # Control-C pressed. Try again.
            except EOFError:
                break  # Control-D pressed.

            arr = text.strip().split(' ')
            command, args = arr[0], arr[1:]

            if command == 'exit':
                break
            elif command in self.commands:
                method = self._command_handlers.get(command)
                if method:
                    try:
                        method(args)
                    except KeyboardInterrupt:
                        self.display.print("\nCommand interrupted by user.", 'red')
                else:
                    print('Command not implemented: {}'.format(command))
            elif command == '':
                continue
            else:
                print('Unknown command: {}'.format(command))
        print('[ash is terminating]')
