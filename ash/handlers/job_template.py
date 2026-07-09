#!/usr/bin/env python

"""Job template context command handler."""

from .base import BaseHandler


class JobTemplateHandler(BaseHandler):
    """Handles commands available in the job_template context: launch, jobs, sync, project."""

    def launch(self, args):
        ash = self.ash
        payload = {}

        for var in ash.current_context.get_asked_variables():
            key, user_input = ash._ask_variable(var)
            payload[key] = user_input

        if ash.current_context.survey_enabled:
            extra_vars = self._handle_survey(ash.current_context.get_survey_spec())
            print(f"Extra vars from survey: {extra_vars}")

            if 'extra_vars' in payload and isinstance(payload['extra_vars'], dict):
                payload['extra_vars'] = {**payload['extra_vars'], **extra_vars}
            elif extra_vars:
                payload['extra_vars'] = extra_vars

        self._execute_payload(ash.current_context, payload)

    def jobs(self, args):
        ash = self.ash
        jobs = ash.current_context.jobs()
        if jobs:
            ash.display.display_jobs(jobs)
        else:
            print("No jobs found for this job template.")

    def sync(self, args):
        ash = self.ash
        project = ash.projects_by_id.get(ash.current_context.project)
        project.sync()
        print(f"Project '{project.name}' sync initiated.")

    def project(self, args):
        self.ash._cd_project([str(self.ash.current_context.project)])
