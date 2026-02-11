#!/usr/bin/env python

from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from prompt_toolkit.lexers import PygmentsLexer
from prompt_toolkit.styles import Style
from termcolor import colored
from os.path import expanduser

import json
import dateutil.parser
from jinja2 import Environment, FileSystemLoader

from .aap import AAP, API, Inventory, JobTemplate, Project, Job
from .completer import AshCompleter
from .commands import ROOT_COMMANDS, CD_COMMANDS, LS_COMMANDS, LS_JOB_TEMPLATE_FILTERS, LS_JOBS_FILTERS, LS_PROJECTS_FILTERS, LS_INVENTORIES_FILTERS, JT_COMMANDS, JOB_COMMANDS, INVENTORY_COMMANDS, PROJECT_COMMANDS
from .colors import COLORS

class Ash(object):
    def __init__(self, baseurl, token, cache):
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
        self.completer = AshCompleter(self)
        history_file_path = expanduser("~/.ash_history")
        self.history = FileHistory(history_file_path)
        self.session = PromptSession(history=self.history, completer=self.completer)
        self.api = API(baseurl, token)
        self.aap = AAP(self.api)
        self.cache = cache
        self._load_all_caches()
        self.current_context = None
        self.colors = COLORS
        self.style = Style.from_dict(self.colors)

    def filter_objects(self, objects, args, filter_definitions):
        if args:
            for arg in [a.lower() for a in args]:
                filter = [filter for filter in filter_definitions.keys() if arg.startswith(filter + ':')]
                if filter:
                    filter_key = filter[0]
                    filter_value = arg.split(':', 1)[1].strip()
                    objects = [
                        obj for obj in objects
                        if filter_value.lower()
                        in obj.data["summary_fields"].get(filter_key, {}).get('name', '').lower()
                        or filter_value.lower()
                        in obj.data["summary_fields"].get(filter_key, {}).get('username', '').lower()
                        or filter_value.lower() in obj.data.get(filter_key, '').lower()
                    ]
                else:
                    objects = [obj for obj in objects if arg in obj.name.lower()]

        return objects

    def status_to_color(self, status):
        if status == 'successful':
            return 'blue'
        elif status in ['failed', 'error', 'canceled']:
            return 'red'
        elif status in ['pending', 'waiting', 'running']:
            return 'yellow'
        else:
            return 'white'

    def display_jobs(self, jobs):
        len_id = max([len(str(j.id)) for j in jobs] + [len("ID")])
        len_name = max([len(j.name) for j in jobs] + [len("Name")])
        len_scm_branch = max([len(j.scm_branch) for j in jobs] + [len("Branch")])
        len_status = max([len(j.status) for j in jobs] + [len("Status")])
        len_created = 11
        len_playbook = max([len(j.playbook) for j in jobs] + [len("Playbook")])
        len_limit = max([len(j.limit) for j in jobs] + [len("Limit")])
        if len_limit > 20:
            len_limit = 20

        format_str = f"{{:<{len_id}}}   {{:<{len_created}}}   {{:<{len_limit}}}   {{:<{len_name}}}   {{:<{len_playbook}}}   {{:<{len_scm_branch}}}   {{:<{len_status}}}"
        print(colored(format_str.format("ID", "Created", "Limit", "Name", "Playbook", "Branch", "Status"), attrs=['bold', 'underline']))
        for job in jobs:
            created = dateutil.parser.isoparse(job.created).astimezone().strftime('%d/%m-%H:%M')
            message = format_str.format(job.id, created, job.limit, job.name, job.playbook, job.scm_branch, job.status)
            color = self.status_to_color(job.status)
            print(colored(message, color, attrs=['bold']))

    # List command implementations
    def __cmd_ls(self, args):
        if len(args) == 0:
            print("Usage: ls <object_type>")
            return

        object_type = args[0]

        if object_type not in LS_COMMANDS.keys():
            print(f"Unknown object type: {object_type}")
            return

        method = getattr(self, f'_Ash__ls_{object_type}', None)
        method(args[1:])

    def __ls_job_templates(self, args):
        if not self.job_templates:
            print("No job templates in cache. Try using 'cache' command.")
            return

        job_templates = self.filter_objects(self.job_templates, args, LS_JOB_TEMPLATE_FILTERS)

        for jt in job_templates:
            print(colored(f"JobTemplate[{jt.id}] - {jt.name} - {jt.playbook}", 'cyan'))

    def __ls_jobs(self, args):
        jobs = self.aap.get_jobs()
        if jobs:
            self.display_jobs(jobs)
        else:
            print("No jobs found.")

    def __ls_inventories(self, args):
        if not self.inventories:
            print("No inventories in cache. Try using 'cache' command.")
            return

        inventories = self.filter_objects(self.inventories, args, LS_INVENTORIES_FILTERS)

        for inv in inventories:
            print(colored(f"Inventory[{inv.id}] - {inv.name} - {inv.total_hosts} hosts", 'green'))

    def __ls_projects(self, args):
        if not self.projects:
            print("No projects in cache. Try using 'cache' command.")
            return

        projects = self.filter_objects(self.projects, args, LS_PROJECTS_FILTERS)

        for proj in projects:
            print(colored(f"Project[{proj.id}] - {proj.name} - {proj.scm_url}", 'yellow'))

    # Select object command implementations
    def __cmd_cd(self, args):
        if len(args) < 2:
            print("Usage: cd <object_type> <name_or_id>")
            return

        object_type = args[0]

        if object_type not in CD_COMMANDS.keys():
            print(f"Unknown object type: {object_type}")
            return

        method = getattr(self, f'_Ash__cd_{object_type}', None)
        method(args[1:])

    def __cd_job_template(self, args):
        identifier = ' '.join(args)
        jt = None
        if identifier.isdigit():
            jt = self.job_templates_by_id.get(int(identifier))
        else:
            matches = [jt for name, jt in self.job_templates_by_name.items() if identifier.lower() in name.lower()]
            if len(matches) == 1:
                jt = matches[0]

        if not jt:
            print(colored(f"Job Template '{identifier}' not found.", 'red'))
            return
        print(colored(f"Switched context to Job Template: ID={jt.id}, Name={jt.name}", 'cyan'))
        self.current_context = jt
        self.commands = JT_COMMANDS.copy()
        self.commands.update(ROOT_COMMANDS)

    def __cd_job(self, args):
        identifier = ' '.join(args)
        job = None
        if identifier.isdigit():
            job = self.aap.get_job(int(identifier))
        else:
            jobs = self.aap.get_jobs()
            matches = [j for j in jobs if identifier.lower() in j.name.lower()]
            if len(matches) == 1:
                job = matches[0]

        if not job:
            print(colored(f"Job '{identifier}' not found.", 'red'))
            return
        print(colored(f"Switched context to Job: ID={job.id}, Name={job.name}", 'magenta'))
        self.current_context = job
        self.commands = JOB_COMMANDS.copy()
        self.commands.update(ROOT_COMMANDS)

    def __cd_inventory(self, args):
        identifier = ' '.join(args)
        inv = None
        if identifier.isdigit():
            inv = self.inventories_by_id.get(int(identifier))
        else:
            matches = [inv for name, inv in self.inventories_by_name.items() if identifier.lower() in name.lower()]
            if len(matches) == 1:
                inv = matches[0]

        if not inv:
            print(colored(f"Inventory '{identifier}' not found.", 'red'))
            return
        print(colored(f"Switched context to Inventory: ID={inv.id}, Name={inv.name}", 'green'))
        self.current_context = inv
        self.commands = INVENTORY_COMMANDS.copy()
        self.commands.update(ROOT_COMMANDS)

    def __cd_project(self, args):
        identifier = ' '.join(args)
        proj = None
        if identifier.isdigit():
            proj = self.projects_by_id.get(int(identifier))
        else:
            matches = [proj for name, proj in self.projects_by_name.items() if identifier.lower() in name.lower()]
            if len(matches) == 1:
                proj = matches[0]
            elif len(matches) > 1:
                for p in matches:
                    if identifier.lower() == p.name.lower():
                        proj = p
                        break
                if not proj:
                    print(colored(f"Multiple projects found matching '{identifier}':", 'red'))
                    for p in matches:
                        print(colored(f"ID={p.id}, Name={p.name}", 'red'))
                    return

        if not proj:
            print(colored(f"Project '{identifier}' not found.", 'red'))
            return
        print(colored(f"Switched context to Project: ID={proj.id}, Name={proj.name}", 'yellow'))
        self.current_context = proj
        self.commands = PROJECT_COMMANDS.copy()
        self.commands.update(ROOT_COMMANDS)

    # Refresh command implementation
    def __cmd_cache(self, args):
        self.cache.clean_cache()
        self._load_all_caches()
        print("Cache refreshed.")

    def __cmd_refresh(self, args):
        self.current_context.refresh()
        print("Context refreshed.")

    def __cmd_info(self, args):
        print(json.dumps(self.current_context.data, indent=4))

    def __cmd_jobs(self, args):
        jobs = self.current_context.jobs()
        if jobs:
            self.display_jobs(jobs)
        else:
            print("No jobs found for this job template.")

    def __cmd_hosts(self, args):
        hosts = self.current_context.get_hosts()
        if hosts:
            for host in hosts:
                print(f"{host.id}: {host.name}")
        else:
            print("No hosts found in this inventory.")

    def __cmd_output(self, args):
        output = self.current_context.print_stdout()

    def __cmd_launch(self, args):
        payload = {}

        for var in self.current_context.get_asked_variables():
            key = var
            default = getattr(self.current_context, var, '')
            default_display = default
            if var == "credential":
                key = "credentials"
                credentials = self.current_context.summary_fields.get('credentials', [])
                default = [cred['id'] for cred in credentials]
                default_display = ",".join([f"{cred['id']}:{cred['name']}" for cred in credentials])

            user_input = self.session.prompt(f"{var} [{default_display}]: ") or default
            if var == "credential" and isinstance(user_input, str):
                user_input = [int(cred.strip()) for cred in user_input.split(',') if cred.strip().isdigit()]
            payload[key] = user_input

        job = self.current_context.launch(payload)

        if job:
            self.current_context = job
            self.commands = JOB_COMMANDS.copy()
            self.commands.update(ROOT_COMMANDS)
            self.__cmd_output([])

    def __cmd_template(self, args):
        self.__cd_job_template(str(self.current_context.job_template))

    def _load_cache(self, object_type):
        objects = self.cache.load_cache(object_type)
        if objects:
            print(f"Loaded {object_type} from cache, use 'cache' command to refresh.")
            return objects
        else:
            print(f"Retrieving and caching {object_type}")
            method = getattr(self.aap, f'get_{object_type}')
            objects = method()
            if not objects:
                return []
            for obj in objects:
                self.cache.insert_cache(object_type, obj)
            print(f"{len(objects)} {object_type} cached.")
            return objects

    def _load_all_caches(self):
        self.inventories = self._load_cache('inventories')
        self.inventories_by_id = {inv.id: inv for inv in self.inventories} if self.inventories else {}
        self.inventories_by_name = {inv.name: inv for inv in self.inventories} if self.inventories else {}

        self.projects = self._load_cache('projects')
        self.projects_by_id = {proj.id: proj for proj in self.projects} if self.projects else {}
        self.projects_by_name = {proj.name: proj for proj in self.projects} if self.projects else {}

        self.job_templates = self._load_cache('job_templates')
        self.job_templates_by_id = {jt.id: jt for jt in self.job_templates} if self.job_templates else {}
        self.job_templates_by_name = {jt.name: jt for jt in self.job_templates} if self.job_templates else {}

    def get_prompt(self):
        prompt = []
        prompt.append(('class:white', 'ash '))
        if self.current_context:
            if isinstance(self.current_context, JobTemplate):
                prompt.append(('class:cyan', f'JobTemplate[{self.current_context.id}] - {self.current_context.name} '))
            elif isinstance(self.current_context, Inventory):
                prompt.append(('class:green', f'Inventory[{self.current_context.id}] - {self.current_context.name} '))
            elif isinstance(self.current_context, Project):
                prompt.append(('class:yellow', f'Project[{self.current_context.id}] - {self.current_context.name} '))
            elif isinstance(self.current_context, Job):
                prompt.append(('class:magenta', f'Job[{self.current_context.id}] - {self.current_context.name} '))

        prompt.append(('class:white', '> '))
        return prompt

    def run(self):
        while True:
            try:
                text = self.session.prompt(self.get_prompt())
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
                method = getattr(self, f'_Ash__cmd_{command}')
                if method:
                    try:
                        method(args)
                    except KeyboardInterrupt:
                        print(colored("\nCommand interrupted by user.", 'red'))
                else:
                    print('Command not implemented: {}'.format(command))
            elif command == '':
                continue
            else:
                print('Unknown command: {}'.format(command))
        print('[ash is terminating]')
