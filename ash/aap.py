#!/usr/bin/env python

"""High-level service class for the Ansible Automation Platform."""

from .models import Inventory, Project, JobTemplate, Job


class AAP:
    def __init__(self, api):
        self.api = api

    def get_inventories(self):
        return self.api.retrieves_objects("inventories", result_limit=0)

    def get_inventory(self, inventory_id):
        response = self.api.get_request(f"inventories/{inventory_id}/")
        if response is None or response.status_code != 200:
            self.api.log_error(response)
            return None
        return Inventory(self.api, response.json())

    def get_projects(self):
        return self.api.retrieves_objects("projects", result_limit=0)

    def get_project(self, project_id):
        response = self.api.get_request(f"projects/{project_id}/")
        if response is None or response.status_code != 200:
            self.api.log_error(response)
            return None
        return Project(self.api, response.json())

    def get_job_templates(self):
        return self.api.retrieves_objects("job_templates", result_limit=0)

    def get_job_template(self, job_template_id):
        response = self.api.get_request(f"job_templates/{job_template_id}/")
        if response is None or response.status_code != 200:
            self.api.log_error(response)
            return None
        return JobTemplate(self.api, response.json())

    def get_jobs(self, filters=None, result_limit=50):
        jobs = self.api.retrieves_objects(
            "jobs", result_limit=result_limit,
            order_by="-finished", filters=filters
        )
        if jobs:
            jobs = list(reversed(jobs))
        return jobs

    def get_job(self, job_id):
        response = self.api.get_request(f"jobs/{job_id}/")
        if response is None or response.status_code != 200:
            self.api.log_error(response)
            return None
        return Job(self.api, response.json())
