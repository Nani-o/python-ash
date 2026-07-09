#!/usr/bin/env python

"""Base handler with shared commands and utilities used across context types."""

import json
import subprocess
import webbrowser

import yaml
from iterfzf import iterfzf


class BaseHandler:
    """Provides shared commands (info, url, open, refresh) and shared utilities
    (ask_variable, handle_survey, retrieve_inventory, validate_payload, execute_payload)
    available across all context types."""

    def __init__(self, ash):
        self.ash = ash

    # ------------------------------------------------------------------ #
    # Shared commands (available in all context-specific command sets)
    # ------------------------------------------------------------------ #

    def sync(self, args):
        if self.ash.current_context_type == 'job_templates':
            self.ash._jt_handler.sync(args)
        else:
            self.ash._project_handler.sync(args)

    def project(self, args):
        if self.ash.current_context_type == 'jobs':
            self.ash._job_handler.project(args)
        else:
            self.ash._jt_handler.project(args)

    def inventory(self, args):
        self.ash._job_handler.inventory(args)

    def info(self, args):
        info = {}
        if args:
            for arg in args:
                info[arg] = self.ash.current_context.data.get(arg, None)
        else:
            info = self.ash.current_context.data
        print(json.dumps(info, indent=4))

    def refresh(self, args):
        self.ash.current_context.refresh()
        if self.ash.current_context_type != 'jobs':
            self.ash.cache.insert_cache(
                self.ash.current_context_type,
                self.ash.current_context.id,
                self.ash.current_context,
            )
        print("Context refreshed.")

    def url(self, args):
        url = self.ash.current_context.absolute_url
        if url:
            try:
                subprocess.run("pbcopy", universal_newlines=True, input=url)
                print(f"{url} copied to clipboard.")
            except Exception:
                print(f"Unable to copy URL to clipboard. Please copy it manually : {url}")
        else:
            print("Unable to get URL for the current context.", 'red')

    def open(self, args):
        url = self.ash.current_context.absolute_url
        if url:
            webbrowser.open(url)
            print(f"Opened {url} in your browser.")
        else:
            print("Unable to get URL for the current context.", 'red')

    # ------------------------------------------------------------------ #
    # Shared utilities
    # ------------------------------------------------------------------ #

    def _multiple_choice_prompt(self, name, description, choices, default=None, required=False, multi=False):
        options = {"--layout=reverse"}
        height = len(choices) + 2
        user_input = None
        if multi:
            options.add("--header=Select one or more options using tab/shift+tab and press Enter when done.")
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
        return user_input

    def _ask_variable(self, var):
        ash = self.ash
        user_input = None
        default_display = None
        multiline = False
        ash.form = None

        if var == "extra_vars":
            multiline = True

        if var == "credential":
            credentials = ash.current_context.summary_fields.get('credentials', [])
            default = ','.join([str(cred['id']) for cred in credentials])
            default_display = ",".join([f"{cred['id']}:{cred['name']}" for cred in credentials])
        elif var == "inventory":
            inventory = ash.current_context.summary_fields.get('inventory', {})
            default = inventory.get('id')
            if default:
                default_display = f"{default}:{inventory.get('name', '')}"
        else:
            default = getattr(ash.current_context, var, '')

        if not default:
            default = ''

        if default_display:
            prompt = f"{var} ({default_display}): "
        else:
            prompt = f"{var}: "

        if multiline:
            ash.display.print("(Multi-line input enabled. Use Meta+Enter or Escape followed by Enter to finish input)", 'yellow')
            prompt += "\n"

        if var == "inventory":
            ash.form = "inventory_form"
            while not user_input:
                user_input = ash.session_wo_history.prompt(prompt, multiline=multiline, completer=ash.form_completer, default=str(default))
                inventories = []
                for inventory in user_input.split(','):
                    if inventory:
                        inventory = self._retrieve_inventory(inventory)
                        if inventory:
                            inventories.append(inventory.id)
                        else:
                            user_input = None
                            break
                user_input = inventories if len(inventories) > 1 else inventories[0] if inventories else None
        else:
            user_input = ash.session_wo_history.prompt(prompt, multiline=multiline, default=str(default))

        if var == "credential" and isinstance(user_input, str):
            user_input = [int(cred.strip()) for cred in user_input.split(',') if cred.strip().isdigit()]
        if var == "extra_vars":
            try:
                user_input = yaml.safe_load(user_input) if user_input else {}
                if user_input is None:
                    user_input = {}
            except yaml.YAMLError as e:
                ash.display.print(f"Error parsing YAML: {e}", 'red')
                return

        return var, user_input

    def _handle_survey(self, survey_spec):
        ash = self.ash
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
                        user_input = ash.session_wo_history.prompt(f"{name} ({description}) [required]: ", multiline=False)
                else:
                    user_input = ash.session_wo_history.prompt(f"{name} ({description}) [{default}]: ", multiline=False) or default
            elif type == 'multiplechoice':
                choices = question.get('choices', [])
                user_input = self._multiple_choice_prompt(name, description, choices, default=default, required=required)
            elif type == 'multiselect':
                choices = question.get('choices', [])
                user_input = self._multiple_choice_prompt(name, description, choices, default=default, required=required, multi=True)

            print(f"Set variable '{variable}' to '{user_input}'")
            extra_vars[variable] = user_input

        return extra_vars

    def _retrieve_inventory(self, reference):
        ash = self.ash
        inventory = None
        if reference.isdigit():
            inventory = ash.inventories_by_id.get(int(reference))
            if not inventory:
                inventory = ash.aap.get_inventory(int(reference))  # Attempt to fetch from API if not in cache
                if inventory:
                    ash.inventories.append(inventory)
                    ash.inventories_by_id[int(reference)] = inventory
                    ash.inventories_by_name[inventory.name] = inventory
                    ash.cache.insert_cache('inventories', inventory.id, inventory)
                else:
                    ash.display.print(f"Invalid inventory ID {reference}. Please enter a valid inventory ID or name.", 'red')
        else:
            inventory = ash.inventories_by_name.get(reference)
            if not inventory:
                ash.display.print(f"Invalid inventory name {reference}. Please enter a valid inventory ID or name.", 'red')
        return inventory

    def _validate_payload(self, payload):
        ash = self.ash
        ash.display.print(f"Final payload for launching the job:\n {json.dumps(payload, indent=4)}", 'green_bold')
        if isinstance(payload.get('inventory'), list):
            inventory_names = [ash.inventories_by_id.get(inv_id).name for inv_id in payload['inventory'] if ash.inventories_by_id.get(inv_id)]
            ash.display.print(f"You specified multiple inventories, jobs will be launched sequentially for each inventory: {', '.join(inventory_names)}", 'yellow_bold')
        user_input = ash.session_wo_history.prompt(f"Are you sure you want to launch this job template with the above parameters? [no]: ", multiline=False) or "no"
        return user_input.lower()

    def _execute_payload(self, template, payload):
        import time
        import sys
        ash = self.ash
        if not self._validate_payload(payload) in ['yes', 'y']:
            ash.display.print("Job launch cancelled.", 'red_bold')
            return

        if isinstance(payload.get('inventory'), list):
            inventory_ids = payload.pop('inventory')
            for inv_id in inventory_ids:
                payload_copy = payload.copy()
                payload_copy['inventory'] = inv_id
                job = template.launch(payload_copy)
                if job:
                    ash.display.print(f"Launched job with ID: {job.id} for inventory ID: {inv_id}", 'yellow')
                    while job.status in ['pending', 'waiting', 'running']:
                        ash.display.print(f"Job with ID: {job.id} for inventory ID: {inv_id} is currently {job.status}. Elapsed time: {str(job.elapsed)}", ash.display.status_to_color(job.status), end='')
                        job.refresh()
                        time.sleep(5)
                        sys.stdout.write('\r')      # Move cursor to the beginning of the line
                        sys.stdout.write('\033[K')  # Clear to the end of the line
                    ash.display.print(f"Job with ID: {job.id} for inventory ID: {inv_id} finished with status: {job.status}. Total elapsed time: {str(job.elapsed)}", ash.display.status_to_color(job.status))
        else:
            job = template.launch(payload)

            if job:
                ash.display.print(f"Launched job with ID: {job.id}, switching context to the new job and displaying output...", 'yellow')
                ash._switch_context(job, 'jobs')
                ash._cmd_output([])
