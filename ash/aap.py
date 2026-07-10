#!/usr/bin/env python

"""Module for interacting with Ansible Automation Platform (AAP) API."""

# pylint: disable=no-member, access-member-before-definition, missing-class-docstring, missing-function-docstring

import requests
from termcolor import colored

import urllib3

from .models import Inventory, Project, JobTemplate, Job, Host
from .object_types import INVENTORIES, PROJECTS, JOB_TEMPLATES, JOBS, HOSTS


OBJECT_FACTORIES = {
    INVENTORIES: Inventory,
    PROJECTS: Project,
    JOB_TEMPLATES: JobTemplate,
    JOBS: Job,
    HOSTS: Host,
}

class API():
    def __init__(self, baseurl, token, api_path, verify_ssl=True):
        self.base_url = baseurl
        self.token = token
        self.api_path = api_path
        self.verify_ssl = verify_ssl
        self.url = requests.compat.urljoin(self.base_url, self.api_path)
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }
        if not self.verify_ssl:
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    def _print_ssl_hint(self):
        print(colored("TLS certificate verification failed.", 'red'))
        print(colored("Hint: add your CA/intermediate certificates to trusted authorities (system trust store or REQUESTS_CA_BUNDLE).", 'yellow'))
        print(colored("If needed for non-production usage, you can disable verification by setting 'verify_ssl: false' in ash config.", 'yellow'))

    def get_request(self, endpoint):
        try:
            response = requests.get(requests.compat.urljoin(self.url, endpoint), headers=self.headers,
                                    verify=self.verify_ssl, timeout=10)
            return response
        except requests.exceptions.SSLError as e:
            print(colored(f"Error connecting to API: {e}", 'red'))
            self._print_ssl_hint()
            return None
        except requests.exceptions.RequestException as e:
            print(colored(f"Error connecting to API: {e}", 'red'))
            return None

    def post_request(self, endpoint, payload):
        try:
            response = requests.post(requests.compat.urljoin(self.url, endpoint), headers=self.headers,
                                     json=payload, verify=self.verify_ssl, timeout=10)
            return response
        except requests.exceptions.SSLError as e:
            print(colored(f"Error connecting to API: {e}", 'red'))
            self._print_ssl_hint()
            return None
        except requests.exceptions.RequestException as e:
            print(colored(f"Error connecting to API: {e}", 'red'))
            return None

    def delete_request(self, endpoint):
        try:
            response = requests.delete(requests.compat.urljoin(self.url, endpoint), headers=self.headers,
                                       verify=self.verify_ssl, timeout=10)
            return response
        except requests.exceptions.SSLError as e:
            print(colored(f"Error connecting to API: {e}", 'red'))
            self._print_ssl_hint()
            return None
        except requests.exceptions.RequestException as e:
            print(colored(f"Error connecting to API: {e}", 'red'))
            return None

    def retrieves_objects(self, object_type, result_limit=10, order_by=None,
                          baseuri=None, filters=None):
        if not result_limit or result_limit > 100:
            page_size = 100
        else:
            page_size = result_limit

        if baseuri:
            url = f"{baseuri}?page_size={page_size}"
        else:
            url = f"{object_type}/?page_size={page_size}"
        if order_by:
            url += f"&order_by={order_by}"
        if filters:
            for key, value in filters.items():
                if key == 'search':
                    values = '+'.join(value)
                    url += f"&{key}={values}"
                else:
                    for v in value:
                        url += f"&{key}={v}"

        response = self.get_request(url)
        if response is None or response.status_code != 200:
            self.log_error(response)
            return None
        data = response.json().get('results', [])

        if not result_limit:
            result_limit = response.json().get('count', 0)

        while response.json().get('next') and len(data) < result_limit:
            endpoint = response.json().get('next').replace(self.api_path, '')
            response = self.get_request(endpoint)
            if response is None or response.status_code != 200:
                self.log_error(response)
                return None
            for item in response.json().get('results', []):
                if len(data) < result_limit:
                    data.append(item)

        objects = [self.instantiate_object(object_type, item) for item in data]
        return objects

    def instantiate_object(self, object_type, data):
        object_factory = OBJECT_FACTORIES.get(object_type)
        if object_factory is None:
            return None

        return object_factory(self, data)

    def log_error(self, response):
        if response is None:
            print(colored("Error: No response from API", 'red'))
        else:
            print(colored(f"Error: {response.status_code} - {response.text}", 'red'))


class AAP():
    def __init__(self, api):
        self.api = api

    def get_inventories(self):
        return self.api.retrieves_objects(INVENTORIES, result_limit=0)

    def get_inventory(self, inventory_id):
        response = self.api.get_request(f"inventories/{inventory_id}/")

        if response is None or response.status_code != 200:
            self.api.log_error(response)
            return None

        return Inventory(self.api, response.json())

    def get_projects(self):
        return self.api.retrieves_objects(PROJECTS, result_limit=0)

    def get_project(self, project_id):
        response = self.api.get_request(f"projects/{project_id}/")

        if response is None or response.status_code != 200:
            self.api.log_error(response)
            return None

        return Project(self.api, response.json())

    def get_job_templates(self):
        return self.api.retrieves_objects(JOB_TEMPLATES, result_limit=0)

    def get_job_template(self, job_template_id):
        response = self.api.get_request(f"job_templates/{job_template_id}/")

        if response is None or response.status_code != 200:
            self.api.log_error(response)
            return None

        return JobTemplate(self.api, response.json())

    def get_jobs(self, filters=None, result_limit=50):
        jobs = self.api.retrieves_objects(JOBS, result_limit=result_limit,
                                          order_by="-finished", filters=filters)
        if jobs:
            jobs = list(reversed(jobs))
        return jobs

    def get_job(self, job_id):
        response = self.api.get_request(f"jobs/{job_id}/")

        if response is None or response.status_code != 200:
            self.api.log_error(response)
            return None

        return Job(self.api, response.json())

