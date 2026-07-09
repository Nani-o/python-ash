#!/usr/bin/env python

"""Command handler mixin for the Ash shell.

Every ``_cmd_*`` method corresponds to a shell command.  Helper methods used
only by the command handlers live here as well.
"""

import json
import sys
import time
import webbrowser
import subprocess
from os import get_terminal_size

import yaml

from .commands import (
    CD_COMMANDS,
    LS_COMMANDS,
    LS_JOB_TEMPLATE_FILTERS,
    LS_JOBS_FILTERS,
    LS_PROJECTS_FILTERS,
    LS_INVENTORIES_FILTERS,
)
from .types import ContextType

# Variables from a previous job that the user should be prompted to re-enter
# when reusing a job (rather than being silently copied from the old job).
_REUSE_PROMPT_VARS = frozenset(('inventory', 'limit', 'job_tags', 'skip_tags'))


class CommandHandlersMixin:
    """Mixin that implements all interactive commands for the Ash shell."""

    # ------------------------------------------------------------------
    # ls
    # ------------------------------------------------------------------

    def _cmd_ls(self, args):
        if not args:
            print("Usage: ls <object_type>")
            return
        object_type = args[0]
        if object_type not in LS_COMMANDS:
            print(f"Unknown object type: {object_type}")
            return
        ls_dispatch = {
            'job_templates': self._ls_job_templates,
            'jobs': self._ls_jobs,
            'inventories': self._ls_inventories,
            'projects': self._ls_projects,
        }
        ls_dispatch[object_type](args[1:])

    def _ls_job_templates(self, args):
        if not self.job_templates:
            print("No job templates in cache. Try using 'cache' command.")
            return
        job_templates = self.filter_objects(self.job_templates, args, LS_JOB_TEMPLATE_FILTERS)
        self.display_job_templates(job_templates)

    def _ls_inventories(self, args):
        if not self.inventories:
            print("No inventories in cache. Try using 'cache' command.")
            return
        inventories = self.filter_objects(self.inventories, args, LS_INVENTORIES_FILTERS)
        self.display_inventories(inventories)

    def _ls_projects(self, args):
        if not self.projects:
            print("No projects in cache. Try using 'cache' command.")
            return
        projects = self.filter_objects(self.projects, args, LS_PROJECTS_FILTERS)
        self.display_projects(projects)

    def _parse_ls_jobs_args(self, args):
        result_limit = 100
        filters = {}
        for arg in [a.lower() for a in args]:
            if ':' in arg and arg.split(':', 1)[0] in LS_JOBS_FILTERS:
                filter_key, filter_value = arg.split(':', 1)
                if filter_key == 'result_limit':
                    try:
                        result_limit = int(filter_value)
                    except ValueError:
                        self.print("Invalid result_limit value. It should be an integer.", 'red')
                        return None, None
                    continue
                filter_key = f"{filter_key}__search"
            else:
                filter_key = "search"
                filter_value = arg

            if filter_key in filters:
                filters[filter_key].append(filter_value)
            else:
                filters[filter_key] = [filter_value]
        return filters, result_limit

    def _ls_jobs(self, args):
        filters, result_limit = self._parse_ls_jobs_args(args)
        jobs = self.aap.get_jobs(filters=filters, result_limit=result_limit)
        if jobs:
            self.display_jobs(jobs)
        else:
            print("No jobs found.")

    # ------------------------------------------------------------------
    # watch
    # ------------------------------------------------------------------

    def _cmd_watch(self, args):
        while True:
            result_limit = get_terminal_size().lines - 2
            filters = self._parse_ls_jobs_args(args)[0]
            jobs = self.aap.get_jobs(filters=filters, result_limit=result_limit)
            sys.stdout.write('\033[H')  # Move cursor to the top-left corner
            sys.stdout.write('\033[J')  # Clear from cursor to the end of the screen
            sys.stdout.flush()
            if jobs:
                self.display_jobs(jobs)
            time.sleep(5)

    # ------------------------------------------------------------------
    # cd
    # ------------------------------------------------------------------

    def _cmd_cd(self, args):
        if not args:
            self._switch_context(None, None)
            return
        if len(args) < 2:
            if args[0] == '-':
                if self.last_context:
                    self._switch_context(self.last_context, self.last_context_type)
                else:
                    self.print("No previous context to switch back to.", 'red')
            else:
                self.print("Usage: cd <object_type> <name_or_id>", 'red')
            return

        object_type = args[0]
        if object_type not in CD_COMMANDS:
            self.print(f"Unknown object type: {object_type}", 'red')
            return

        cd_dispatch = {
            'job_template': self._cd_job_template,
            'inventory': self._cd_inventory,
            'project': self._cd_project,
            'job': self._cd_job,
        }
        cd_dispatch[object_type](args[1:])

    def _cd_job_template(self, args):
        identifier = ' '.join(args)
        if identifier.isdigit():
            jt = self.job_templates_by_id.get(int(identifier))
        else:
            jt = self._find_matching_objects(self.job_templates, identifier)
        if not jt:
            self.print(f"Job Template '{identifier}' not found.", 'red')
            return
        self._switch_context(jt, ContextType.JOB_TEMPLATES)

    def _cd_job(self, args):
        identifier = ' '.join(args)
        if identifier.isdigit():
            job = self.aap.get_job(int(identifier))
        else:
            jobs = list(reversed(self.aap.get_jobs(filters={'search': identifier}, result_limit=100)))
            job = None
            if jobs:
                jobs_list = [
                    "{}: {} - {:<15} {} {}".format(
                        j.id, j.name, self.parse_label(j.limit, 15),
                        j.status, self.parse_label(j.created)
                    )
                    for j in jobs
                ]
                selection = self._multiple_choice_prompt(
                    "Job",
                    f"Multiple jobs found matching '{identifier}'. Please select one:",
                    jobs_list, required=True
                )
                if selection:
                    job_id = int(selection.split(':', 1)[0])
                    job = next((j for j in jobs if j.id == job_id), None)
        if not job:
            self.print(f"Job '{identifier}' not found.", 'red')
            return
        self._switch_context(job, ContextType.JOBS)

    def _cd_inventory(self, args):
        identifier = ' '.join(args)
        if identifier.isdigit():
            inv = self.inventories_by_id.get(int(identifier))
        else:
            inv = self._find_matching_objects(self.inventories, identifier)
        if not inv:
            self.print(f"Inventory '{identifier}' not found.", 'red')
            return
        self._switch_context(inv, ContextType.INVENTORIES)

    def _cd_project(self, args):
        identifier = ' '.join(args)
        if identifier.isdigit():
            proj = self.projects_by_id.get(int(identifier))
        else:
            proj = self._find_matching_objects(self.projects, identifier)
        if not proj:
            self.print(f"Project '{identifier}' not found.", 'red')
            return
        self._switch_context(proj, ContextType.PROJECTS)

    def _find_matching_objects(self, objects, identifier):
        matches = [obj for obj in objects if identifier.lower() in obj.name.lower()]
        exact_matches = [obj for obj in matches if identifier.lower() == obj.name.lower()]
        if len(exact_matches) == 1:
            return exact_matches[0]
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            user_input = self._multiple_choice_prompt(
                "Multiple matches found",
                f"Multiple objects found matching '{identifier}'. Please select one:",
                [f"{obj.id}: {obj.name}" for obj in matches],
                required=True
            )
            if user_input:
                selected_id = int(user_input.split(':', 1)[0])
                return next((obj for obj in matches if obj.id == selected_id), None)
        return None

    # ------------------------------------------------------------------
    # cache / refresh
    # ------------------------------------------------------------------

    def _cmd_cache(self, args):
        cache_loaders = {
            'inventories': self._load_inventories_cache,
            'projects': self._load_projects_cache,
            'job_templates': self._load_job_templates_cache,
        }
        if args:
            if args[0] not in cache_loaders:
                print(
                    f"Unknown cache type: {args[0]}. "
                    f"Valid types are: {', '.join(cache_loaders.keys())}."
                )
                return
            self.cache.clean_cache(args[0])
            cache_loaders[args[0]]()
        else:
            self.cache.clean_cache()
            self._load_all_caches()
        print("Cache refreshed.")

    def _cmd_refresh(self, args):
        self.current_context.refresh()
        if self.current_context_type != ContextType.JOBS:
            self.cache.insert_cache(
                self.current_context_type, self.current_context.id, self.current_context
            )
        print("Context refreshed.")

    # ------------------------------------------------------------------
    # info / url / open
    # ------------------------------------------------------------------

    def _cmd_url(self, args):
        url = self.current_context.absolute_url
        if url:
            try:
                subprocess.run("pbcopy", universal_newlines=True, input=url)
                print(f"{url} copied to clipboard.")
            except Exception:
                print(f"Unable to copy URL to clipboard. Please copy it manually: {url}")
        else:
            print("Unable to get URL for the current context.")

    def _cmd_open(self, args):
        url = self.current_context.absolute_url
        if url:
            webbrowser.open(url)
            print(f"Opened {url} in your browser.")
        else:
            print("Unable to get URL for the current context.")

    def _cmd_info(self, args):
        if args:
            info = {arg: self.current_context.data.get(arg) for arg in args}
        else:
            info = self.current_context.data
        print(json.dumps(info, indent=4))

    # ------------------------------------------------------------------
    # context-specific object commands
    # ------------------------------------------------------------------

    def _cmd_jobs(self, args):
        jobs = self.current_context.jobs()
        if jobs:
            self.display_jobs(jobs)
        else:
            print("No jobs found for this job template.")

    def _cmd_hosts(self, args):
        hosts = self.current_context.get_hosts()
        if hosts:
            for host in hosts:
                print(f"{host.id}: {host.name}")
        else:
            print("No hosts found in this inventory.")

    def _cmd_add_hosts(self, args):
        self.print(
            "(Multi-line input enabled. Use Meta+Enter or Escape followed by Enter to finish input)",
            'yellow'
        )
        user_input = self.session_wo_history.prompt("Hosts to add (one per line):\n", multiline=True)
        results = self.current_context.add_hosts(user_input.splitlines())
        for host, result in results.items():
            if result is not None:
                if result.status_code == 201:
                    self.print(f"{host}: Host added successfully.", 'green')
                elif result.status_code == 400:
                    self.print(
                        f"{host}: {result.json().get('__all__', ['Unknown error'])[0]}", 'red'
                    )
                else:
                    self.print(
                        f"{host}: Failed to add host. Status code: {result.status_code}", 'red'
                    )

    def _cmd_clear_hosts(self, args):
        confirmation = (
            self.session_wo_history.prompt(
                "Are you sure you want to delete all hosts from this inventory? "
                "This action cannot be undone. [no]: ",
                multiline=False
            ) or "no"
        )
        if confirmation.lower() in ('yes', 'y'):
            results = self.current_context.clear_hosts()
            for host, result in results.items():
                if result is not None:
                    if result.status_code == 204:
                        self.print(f"{host}: Host deleted successfully.", 'green')
                    else:
                        self.print(
                            f"{host}: Failed to delete host. Status code: {result.status_code}",
                            'red'
                        )
        else:
            self.print("Operation cancelled.", 'yellow')

    def _cmd_relaunch(self, args):
        job = self.current_context.relaunch()
        if job:
            self.print(
                f"Relaunched job with ID: {job.id}, "
                "switching context to the new job and displaying output...",
                'yellow'
            )
            self._switch_context(job, ContextType.JOBS)
            self._cmd_output([])
        else:
            self.print("Failed to relaunch the job.", 'red')

    def _cmd_cancel(self, args):
        if self.current_context.cancel():
            self.print(f"Cancelled job with ID: {self.current_context.id}", 'yellow')
        else:
            self.print("Failed to cancel the job.", 'red')

    def _cmd_output(self, args):
        self.current_context.print_stdout()

    def _cmd_template(self, args):
        self._cd_job_template([str(self.current_context.job_template)])

    def _cmd_project(self, args):
        self._cd_project([str(self.current_context.project)])

    def _cmd_inventory(self, args):
        self._cd_inventory([str(self.current_context.inventory)])

    def _cmd_sync(self, args):
        if self.current_context_type == ContextType.JOB_TEMPLATES:
            project = self.projects_by_id.get(self.current_context.project)
        else:
            project = self.current_context
        project.sync()
        print(f"Project '{project.name}' sync initiated.")

    # ------------------------------------------------------------------
    # launch / reuse helpers
    # ------------------------------------------------------------------

    def _multiple_choice_prompt(self, name, description, choices, default=None,
                                required=False, multi=False):
        from iterfzf import iterfzf
        options = {"--layout=reverse"}
        height = len(choices) + 2
        if multi:
            options.add("--header=Select one or more options using tab/shift+tab and press Enter when done.")
            height += 1
        options.add(f"--height={height}")
        user_input = None
        if required and not default:
            while not user_input:
                user_input = iterfzf(
                    choices, prompt=f"{name} ({description}) [required]: ",
                    __extra__=options, multi=multi
                )
        else:
            if default and not multi:
                choices = sorted(choices, key=lambda x: 0 if x == default else 1)
            user_input = (
                iterfzf(
                    choices, prompt=f"{name} ({description}) [{default}]: ",
                    __extra__=options, multi=multi
                ) or default
            )
        return user_input

    def _handle_survey(self, survey_spec):
        extra_vars = {}
        for question in survey_spec:
            default = question.get('default', '')
            name = question['question_name']
            description = question['question_description']
            variable = question['variable']
            required = question['required']
            q_type = question['type']

            user_input = None
            if q_type == 'text':
                if required and not default:
                    while not user_input:
                        user_input = self.session_wo_history.prompt(
                            f"{name} ({description}) [required]: ", multiline=False
                        )
                else:
                    user_input = (
                        self.session_wo_history.prompt(
                            f"{name} ({description}) [{default}]: ", multiline=False
                        ) or default
                    )
            elif q_type == 'multiplechoice':
                choices = question.get('choices', [])
                user_input = self._multiple_choice_prompt(
                    name, description, choices, default=default, required=required
                )
            elif q_type == 'multiselect':
                choices = question.get('choices', [])
                user_input = self._multiple_choice_prompt(
                    name, description, choices, default=default, required=required, multi=True
                )

            print(f"Set variable '{variable}' to '{user_input}'")
            extra_vars[variable] = user_input

        return extra_vars

    # --- per-variable-type ask helpers ---

    def _ask_credential_var(self):
        var = 'credential'
        credentials = self.current_context.summary_fields.get('credentials', [])
        default = ','.join([str(cred['id']) for cred in credentials])
        default_display = ",".join([f"{cred['id']}:{cred['name']}" for cred in credentials])
        prompt = f"{var} ({default_display}): " if default_display else f"{var}: "
        user_input = self.session_wo_history.prompt(prompt, multiline=False, default=str(default))
        if isinstance(user_input, str):
            user_input = [
                int(cred.strip()) for cred in user_input.split(',') if cred.strip().isdigit()
            ]
        return var, user_input

    def _ask_inventory_var(self):
        var = 'inventory'
        self.form = "inventory_form"
        inventory = self.current_context.summary_fields.get('inventory', {})
        default = inventory.get('id', '')
        default_display = f"{default}:{inventory.get('name', '')}" if default else None
        prompt = f"{var} ({default_display}): " if default_display else f"{var}: "
        if not default:
            default = ''
        user_input = None
        while not user_input:
            user_input = self.session_wo_history.prompt(
                prompt, multiline=False,
                completer=self.form_completer, default=str(default)
            )
            inventories = []
            for inv_ref in user_input.split(','):
                if inv_ref:
                    inv_obj = self._retrieve_inventory(inv_ref)
                    if inv_obj:
                        inventories.append(inv_obj.id)
                    else:
                        user_input = None
                        break
        result = inventories if len(inventories) > 1 else (inventories[0] if inventories else None)
        return var, result

    def _ask_extra_vars_var(self):
        var = 'extra_vars'
        default = getattr(self.current_context, var, '') or ''
        self.print(
            "(Multi-line input enabled. Use Meta+Enter or Escape followed by Enter to finish input)",
            'yellow'
        )
        user_input = self.session_wo_history.prompt(f"{var}: \n", multiline=True, default=str(default))
        try:
            user_input = yaml.safe_load(user_input) if user_input else {}
            if user_input is None:
                user_input = {}
        except yaml.YAMLError as e:
            self.print(f"Error parsing YAML: {e}", 'red')
            return None
        return var, user_input

    def _ask_simple_var(self, var):
        default = getattr(self.current_context, var, '') or ''
        user_input = self.session_wo_history.prompt(f"{var}: ", multiline=False, default=str(default))
        return var, user_input

    def _ask_variable(self, var):
        self.form = None
        var_handlers = {
            'inventory': self._ask_inventory_var,
            'credential': self._ask_credential_var,
            'extra_vars': self._ask_extra_vars_var,
        }
        handler = var_handlers.get(var)
        if handler:
            return handler()
        return self._ask_simple_var(var)

    def _retrieve_inventory(self, reference):
        if reference.isdigit():
            inventory = self.inventories_by_id.get(int(reference))
            if not inventory:
                inventory = self.aap.get_inventory(int(reference))
                if inventory:
                    self.inventories.append(inventory)
                    self.inventories_by_id[int(reference)] = inventory
                    self.inventories_by_name[inventory.name] = inventory
                    self.cache.insert_cache('inventories', inventory.id, inventory)
                else:
                    self.print(
                        f"Invalid inventory ID {reference}. "
                        "Please enter a valid inventory ID or name.", 'red'
                    )
        else:
            inventory = self.inventories_by_name.get(reference)
            if not inventory:
                self.print(
                    f"Invalid inventory name {reference}. "
                    "Please enter a valid inventory ID or name.", 'red'
                )
        return inventory

    def _validate_payload(self, payload):
        self.print(
            f"Final payload for launching the job:\n {json.dumps(payload, indent=4)}",
            'green_bold'
        )
        if isinstance(payload.get('inventory'), list):
            inventory_names = [
                self.inventories_by_id.get(inv_id).name
                for inv_id in payload['inventory']
                if self.inventories_by_id.get(inv_id)
            ]
            self.print(
                f"You specified multiple inventories, jobs will be launched sequentially "
                f"for each inventory: {', '.join(inventory_names)}",
                'yellow_bold'
            )
        user_input = (
            self.session_wo_history.prompt(
                "Are you sure you want to launch this job template "
                "with the above parameters? [no]: ",
                multiline=False
            ) or "no"
        )
        return user_input.lower()

    def _execute_payload(self, template, payload):
        if self._validate_payload(payload) not in ('yes', 'y'):
            self.print("Job launch cancelled.", 'red_bold')
            return

        if isinstance(payload.get('inventory'), list):
            inventory_ids = payload.pop('inventory')
            for inv_id in inventory_ids:
                payload_copy = {**payload, 'inventory': inv_id}
                job = template.launch(payload_copy)
                if job:
                    self.print(
                        f"Launched job with ID: {job.id} for inventory ID: {inv_id}", 'yellow'
                    )
                    while job.status in ('pending', 'waiting', 'running'):
                        self.print(
                            f"Job with ID: {job.id} for inventory ID: {inv_id} "
                            f"is currently {job.status}. Elapsed time: {str(job.elapsed)}",
                            self.status_to_color(job.status), end=''
                        )
                        job.refresh()
                        time.sleep(5)
                        sys.stdout.write('\r')
                        sys.stdout.write('\033[K')
                    self.print(
                        f"Job with ID: {job.id} for inventory ID: {inv_id} "
                        f"finished with status: {job.status}. Total elapsed time: {str(job.elapsed)}",
                        self.status_to_color(job.status)
                    )
        else:
            job = template.launch(payload)
            if job:
                self.print(
                    f"Launched job with ID: {job.id}, "
                    "switching context to the new job and displaying output...",
                    'yellow'
                )
                self._switch_context(job, ContextType.JOBS)
                self._cmd_output([])

    def _cmd_launch(self, args):
        payload = {}
        for var in self.current_context.get_asked_variables():
            result = self._ask_variable(var)
            if result is None:
                return
            key, user_input = result
            payload[key] = user_input

        if self.current_context.survey_enabled:
            extra_vars = self._handle_survey(self.current_context.get_survey_spec())
            print(f"Extra vars from survey: {extra_vars}")
            if 'extra_vars' in payload and isinstance(payload['extra_vars'], dict):
                payload['extra_vars'] = {**payload['extra_vars'], **extra_vars}
            elif extra_vars:
                payload['extra_vars'] = extra_vars

        self._execute_payload(self.current_context, payload)

    def _cmd_reuse(self, args):
        payload = {}
        job = self.current_context

        template = self.job_templates_by_id.get(job.job_template)
        if not template:
            self.print("Original job template not found in cache. Cannot reuse the job.", 'red')
            return

        for var in template.get_asked_variables():
            if var in _REUSE_PROMPT_VARS:
                result = self._ask_variable(var)
                if result is None:
                    return
                key, user_input = result
                payload[key] = user_input
            elif var == 'credential':
                payload['credential'] = [
                    cred['id'] for cred in job.summary_fields.get('credentials', [])
                ]
            elif var == 'variables':
                pass
            else:
                payload[var] = getattr(job, var, None)

        payload['extra_vars'] = json.loads(job.extra_vars) if job.extra_vars else {}
        self._execute_payload(template, payload)
