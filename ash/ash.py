#!/usr/bin/env python

from collections import OrderedDict
from prompt_toolkit import PromptSession
from prompt_toolkit import print_formatted_text
from prompt_toolkit.formatted_text import FormattedText
from prompt_toolkit.history import FileHistory
from prompt_toolkit.lexers import PygmentsLexer
from prompt_toolkit.styles import Style
from os.path import expanduser
from iterfzf import iterfzf

import json
import webbrowser
import dateutil.parser
from jinja2 import Environment, FileSystemLoader

from .aap import AAP, API, Inventory, JobTemplate, Project, Job
from .completer import AshCompleter
from .commands import ROOT_COMMANDS, CD_COMMANDS, LS_COMMANDS, LS_JOB_TEMPLATE_FILTERS, LS_JOBS_FILTERS, LS_PROJECTS_FILTERS, LS_INVENTORIES_FILTERS, JT_COMMANDS, JOB_COMMANDS, INVENTORY_COMMANDS, PROJECT_COMMANDS
from .colors import COLORS

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
        self.api = API(config.base_url, config.token, api_path=api_path)
        self.aap = AAP(self.api)
        self.cache = cache
        self._load_all_caches()
        self.current_context = None
        self.current_context_type = None
        self.colors = COLORS
        history_file_path = expanduser("~/.ash_history")
        self.history = FileHistory(history_file_path)
        self.completer = AshCompleter(self)
        self.style = Style.from_dict(self.colors)
        self.session = PromptSession(history=self.history, style=self.style)

    def filter_objects(self, objects, args, filter_definitions):
        if args:
            for arg in [a.lower() for a in args]:
                filter = [filter for filter in filter_definitions.keys() if arg.startswith(filter + ':')]
                if filter:
                    filter_key = filter[0]
                    filter_value = arg.split(':', 1)[1].strip()
                    if not filter_value:
                        self.print(f"Invalid filter format: '{arg}'. Expected format is 'filter:value'.", 'red')
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

    def print(self, message, class_name=None, attrs=None):
        if class_name:
            print_formatted_text(FormattedText([(f'class:{class_name}', message)]), style=self.style)
        else:
            print(message)

    def object_to_color(self, obj):
        if isinstance(obj, JobTemplate):
            return 'cyan'
        elif isinstance(obj, Inventory):
            return 'green'
        elif isinstance(obj, Project):
            return 'orange'
        elif isinstance(obj, Job):
            return self.status_to_color(obj.status)
        else:
            return 'white'

    def status_to_color(self, status):
        if status == 'successful':
            return 'blue'
        elif status in ['failed', 'error']:
            return 'red'
        elif status == 'canceled':
            return 'magenta'
        elif status in ['pending', 'waiting', 'running']:
            return 'yellow'
        else:
            return 'white'

    def parse_label(self, label, max_length):
        # if string is ISO datetime, parse and format it
        try:
            dt = dateutil.parser.isoparse(label)
            label = dt.astimezone().strftime('%d/%m-%H:%M')
        except (ValueError, TypeError):
            pass
        if len(label) <= max_length:
            return label
        else:
            return label[:max_length-3] + '...'

    def display_jobs(self, jobs):
        self.display_by_columns(jobs, ['id', 'created', 'limit', 'name', 'playbook', 'scm_branch', 'status'])

    def display_job_templates(self, job_templates):
        self.display_by_columns(job_templates, ['id', 'name', 'playbook'])

    def display_inventories(self, inventories):
        self.display_by_columns(inventories, ['id', 'name', 'total_hosts'])

    def display_projects(self, projects):
        self.display_by_columns(projects, ['id', 'name', 'scm_url'])

    def display_by_columns(self, objects, columns):
        column_widths = {}
        for col in columns:
            if col in ['created', 'modified', 'finished']:
                max_len = 11
            else:
                max_len = max([len(str(getattr(obj, col))) for obj in objects] + [len(col)])
            if col == 'limit' and max_len > 30:
                max_len = 30
            column_widths[col] = max_len

        format_str = "   ".join([f"{{:<{column_widths[col]}}}" for col in columns])
        header = format_str.format(*[col.capitalize() for col in columns])
        self.print(header, 'headers')
        for obj in objects:
            message = format_str.format(*[self.parse_label(str(getattr(obj, col)), column_widths[col]) for col in columns])
            color = self.object_to_color(obj)
            self.print(message, color + '_bold')

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
        self.display_job_templates(job_templates)

    def __ls_jobs(self, args):
        result_limit = 100
        if args:
            filters = {}
            for arg in [a.lower() for a in args]:
                if ':' in arg and arg.split(':', 1)[0] in LS_JOBS_FILTERS.keys():
                    filter_key, filter_value = arg.split(':', 1)
                    if filter_key == 'result_limit':
                        try:
                            filter_value = int(filter_value)
                        except ValueError:
                            self.print("Invalid result_limit value. It should be an integer.", 'red')
                            return
                        result_limit = filter_value
                        continue
                    filter_key = f"{filter_key}__search"
                else:
                    filter_key = "search"
                    filter_value = arg

                if filter_key in filters:
                    filters[filter_key].append(filter_value)
                else:
                    filters[filter_key] = [filter_value]
        else:
            filters = None
        jobs = self.aap.get_jobs(filters=filters, result_limit=result_limit)
        if jobs:
            self.display_jobs(jobs)
        else:
            print("No jobs found.")

    def __ls_inventories(self, args):
        if not self.inventories:
            print("No inventories in cache. Try using 'cache' command.")
            return

        inventories = self.filter_objects(self.inventories, args, LS_INVENTORIES_FILTERS)
        self.display_inventories(inventories)

    def __ls_projects(self, args):
        if not self.projects:
            print("No projects in cache. Try using 'cache' command.")
            return

        projects = self.filter_objects(self.projects, args, LS_PROJECTS_FILTERS)
        self.display_projects(projects)

    # Change directory command implementations
    #
    # Note: The CD commands will attempt to find the specified object by ID first, then by name (case-insensitive, partial match).
    # If multiple matches are found by name, it will list the matches and ask the user to refine their input.
    # The context is switched to the specified object and the available commands are updated accordingly.

    def __switch_context(self, context, context_type):
        self.current_context = context
        self.current_context_type = context_type
        self.commands = self.__get_commands_for_context(context_type)

    def __get_commands_for_context(self, context_type):
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

    def __cmd_cd(self, args):
        if len(args) == 0:
            self.__switch_context(None, None)
            print("Switched to root context.")
            return
        elif len(args) < 2:
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
            self.print(f"Job Template '{identifier}' not found.", 'red')
            return
        self.print(f"Switched context to Job Template: ID={jt.id}, Name={jt.name}", 'cyan')
        self.__switch_context(jt, 'job_templates')

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
            self.print(f"Job '{identifier}' not found.", 'red')
            return
        self.print(f"Switched context to Job: ID={job.id}, Name={job.name}", self.status_to_color(job.status))
        self.__switch_context(job, 'jobs')

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
            self.print(f"Inventory '{identifier}' not found.", 'red')
            return
        self.print(f"Switched context to Inventory: ID={inv.id}, Name={inv.name}", 'green')
        self.__switch_context(inv, 'inventories')

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
                    self.print(f"Multiple projects found matching '{identifier}':", 'red')
                    for p in matches:
                        self.print(f"ID={p.id}, Name={p.name}", 'red')
                    return

        if not proj:
            self.print(f"Project '{identifier}' not found.", 'red')
            return
        self.print(f"Switched context to Project: ID={proj.id}, Name={proj.name}", 'orange')
        self.__switch_context(proj, 'projects')

    # Refresh commands implementation
    #
    # The 'cache' command will clear the local cache and re-fetch all inventories, projects, and job templates from the API.
    # The 'refresh' command will refresh the current context, which is useful for updating the details of the current object
    # without refreshing the entire cache.
    #

    def __cmd_cache(self, args):
        self.cache.clean_cache()
        self._load_all_caches()
        print("Cache refreshed.")

    def __cmd_refresh(self, args):
        self.current_context.refresh()
        if self.current_context_type != 'jobs':
            self.cache.insert_cache(self.current_context_type, self.current_context.id, self.current_context)
        print("Context refreshed.")

    def __cmd_open(self, args):
        url = self.current_context.absolute_url
        if url:
            webbrowser.open(url)
            print(f"Opened {url} in your browser.")
        else:
            print("Unable to get URL for the current context.", 'red')

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

    def __cmd_relaunch(self, args):
        job = self.current_context.relaunch()
        if job:
            self.print(f"Relaunched job with ID: {job.id}, switching context to the new job and displaying output...", 'yellow')
            self.__switch_context(job, 'jobs')
            self.__cmd_output([])
        else:
            self.print("Failed to relaunch the job.", 'red')

    def __cmd_cancel(self, args):
        if self.current_context.cancel():
            self.print(f"Cancelled job with ID: {self.current_context.id}", 'yellow')
        else:
            self.print("Failed to cancel the job.", 'red')

    def __cmd_reuse(self, args):
        self.print("Not implemented yet.", 'red')

    def __cmd_output(self, args):
        output = self.current_context.print_stdout()

    def __multiple_choice_prompt(self, name, description, variable, choices, default=None, required=False, multi=False):
        options = {"--layout=reverse"}
        height = len(choices) + 2
        user_input = None
        if multi:
            options.add(f"--header=Select one or more options using tab/shift+tab and press Enter when done.")
            height += 1
        options.add(f"--height={height}")
        if required and not default:
            while not user_input:
                user_input = iterfzf(choices, prompt=f"{name} ({description}) [required]: ", __extra__=options, multi=multi)
        else:
            # Reorder the list so that the default value(s) appear at the top
            if default and not multi:
                choices = sorted(choices, key=lambda x: 0 if x == default else 1)
            user_input = iterfzf(choices, prompt=f"{name} ({description}) [{default}]: ", __extra__=options, multi=multi) or default
        print(f"Set variable '{variable}' to '{user_input}'")
        return user_input

    def __handle_survey(self, survey_spec):
        extra_vars = {}
        for question in survey_spec:
            default = question.get('default', '')
            name = question['question_name']
            description = question['question_description']
            variable = question['variable']
            required = question['required']
            type = question['type']

            user_input = None
            if type == 'text':
                if required and not default:
                    while not user_input:
                        user_input = self.session.prompt(f"{name} ({description}) [required]: ")
                else:
                    user_input = self.session.prompt(f"{name} ({description}) [{default}]: ") or default
                print(f"Set variable '{variable}' to '{user_input}'")
            elif type == 'multiplechoice':
                choices = question.get('choices', [])
                user_input = self.__multiple_choice_prompt(name, description, variable, choices, default=default, required=required)
            elif type == 'multiselect':
                choices = question.get('choices', [])
                user_input = self.__multiple_choice_prompt(name, description, variable, choices, default=default, required=required, multi=True)

            extra_vars[variable] = user_input

        return extra_vars


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

        if self.current_context.survey_enabled:
            self.print("This job template has a survey. Not implemented yet.", 'red')
            extra_vars = self.__handle_survey(self.current_context.get_survey_spec())
            print(f"Extra vars from survey: {extra_vars}")

            if 'extra_vars' in payload and isinstance(payload['extra_vars'], dict):
                payload['extra_vars'] = {**payload['extra_vars'], **extra_vars}
            elif extra_vars:
                payload['extra_vars'] = extra_vars

        user_input = self.session.prompt(f"Are you sure you want to launch this job template with the above parameters? [no]: ")or "no"
        if not user_input.lower() in ['yes', 'y']:
            self.print("Job launch cancelled.", 'red_bold')
            return

        job = self.current_context.launch(payload)

        if job:
            self.print(f"Launched job with ID: {job.id}, switching context to the new job and displaying output...", 'yellow')
            self.__switch_context(job, 'jobs')
            self.__cmd_output([])

    def __cmd_sync(self, args):
        if self.current_context_type == 'job_templates':
            project = self.projects_by_id.get(self.current_context.project)
        else:
            project = self.current_context
        project.sync()
        print(f"Project '{project.name}' sync initiated.")

    def __cmd_template(self, args):
        self.__cd_job_template([str(self.current_context.job_template)])

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
                self.cache.insert_cache(object_type, obj.id, obj)
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
                prompt.append(('class:orange', f'Project[{self.current_context.id}] - {self.current_context.name} '))
            elif isinstance(self.current_context, Job):
                color = self.status_to_color(self.current_context.status)
                prompt.append((f'class:{color}', f'Job[{self.current_context.id}] - {self.current_context.name} - {self.current_context.status} '))

        prompt.append(('class:white', '> '))
        return prompt

    def run(self):
        while True:
            try:
                text = self.session.prompt(self.get_prompt(), completer=self.completer)
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
                        self.print("\nCommand interrupted by user.", 'red')
                else:
                    print('Command not implemented: {}'.format(command))
            elif command == '':
                continue
            else:
                print('Unknown command: {}'.format(command))
        print('[ash is terminating]')
