#!/usr/bin/env python

"""Job context command handler."""

import json

from .base import BaseHandler


class JobHandler(BaseHandler):
    """Handles commands available in the job context: relaunch, reuse, cancel, output,
    inventory, project, template."""

    def relaunch(self, args):
        ash = self.ash
        job = ash.current_context.relaunch()
        if job:
            ash.display.print(f"Relaunched job with ID: {job.id}, switching context to the new job and displaying output...", 'yellow')
            ash._switch_context(job, 'jobs')
            ash._cmd_output([])
        else:
            ash.display.print("Failed to relaunch the job.", 'red')

    def reuse(self, args):
        ash = self.ash
        payload = {}
        job = ash.current_context

        template = ash.job_templates_by_id.get(job.job_template)
        if not template:
            ash.display.print("Original job template not found in cache. Cannot reuse the job.", 'red')
            return

        for var in template.get_asked_variables():
            if var in ['inventory', 'limit', 'job_tags', 'skip_tags']:
                key, user_input = ash._ask_variable(var)
                payload[key] = user_input
            elif var == 'credential':
                payload['credential'] = [cred['id'] for cred in job.summary_fields.get('credentials', [])]
            elif var == 'variables':
                pass
            else:
                payload[var] = getattr(job, var, None)

        payload['extra_vars'] = json.loads(job.extra_vars) if job.extra_vars else {}

        self._execute_payload(template, payload)

    def cancel(self, args):
        ash = self.ash
        if ash.current_context.cancel():
            ash.display.print(f"Cancelled job with ID: {ash.current_context.id}", 'yellow')
        else:
            ash.display.print("Failed to cancel the job.", 'red')

    def output(self, args):
        self.ash.current_context.print_stdout()

    def inventory(self, args):
        self.ash._cd_inventory([str(self.ash.current_context.inventory)])

    def project(self, args):
        self.ash._cd_project([str(self.ash.current_context.project)])

    def template(self, args):
        self.ash._cd_job_template([str(self.ash.current_context.job_template)])
