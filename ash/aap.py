#!/usr/bin/env python

"""Module for interacting with Ansible Automation Platform (AAP) API."""

# pylint: disable=no-member, access-member-before-definition, missing-class-docstring, missing-function-docstring

import time

import requests
from termcolor import colored

import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class API():
    def __init__(self, baseurl, token, api_path="/api/v2/"):
        self.base_url = baseurl
        self.token = token
        self.api_path = api_path
        if not self.base_url.endswith('/'):
            self.base_url += '/'
        self.url = f"{self.base_url}{self.api_path}"
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }

    def get_request(self, endpoint):
        try:
            response = requests.get(self.url + endpoint, headers=self.headers,
                                    verify=False, timeout=10)
            return response
        except requests.exceptions.RequestException as e:
            print(colored(f"Error connecting to API: {e}", 'red'))
            return None

    def post_request(self, endpoint, payload):
        try:
            response = requests.post(self.url + endpoint, headers=self.headers,
                                     json=payload, verify=False, timeout=10)
            return response
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
        if object_type == "inventories":
            return Inventory(self, data)
        if object_type == "projects":
            return Project(self, data)
        if object_type == "job_templates":
            return JobTemplate(self, data)
        if object_type == "jobs":
            return Job(self, data)

        return None

class AAP():
    def __init__(self, api):
        self.api = api

    def get_inventories(self):
        return self.api.retrieves_objects("inventories", result_limit=0)

    def get_projects(self):
        return self.api.retrieves_objects("projects", result_limit=0)

    def get_job_templates(self):
        return self.api.retrieves_objects("job_templates", result_limit=0)

    def get_jobs(self, filters=None, result_limit=50):
        jobs = self.api.retrieves_objects("jobs", result_limit=result_limit,
                                          order_by="-finished", filters=filters)
        if jobs:
            jobs = list(reversed(jobs))
        return jobs

    def get_job(self, job_id):
        response = self.api.get_request(f"jobs/{job_id}/")

        if response is None or response.status_code != 200:
            self.log_error(response)
            return None

        return Job(self.api, response.json())

class BaseObject():
    def __init__(self, api, data):
        self.api = api
        self.init_vars(data)

    def init_vars(self, data):
        for k, v in data.items():
            setattr(self, k, v)
        self.data = data

    def refresh(self):
        response = self.api.get_request(self.uri)

        if response is None or response.status_code != 200:
            return
        self.init_vars(response.json())

    def log_error(self, response):
        if response is None:
            print(colored("Error: No response from API", 'red'))
        else:
            print(colored(f"Error: {response.status_code} - {response.text}", 'red'))

class JobTemplate(BaseObject):
    def __init__(self, api, data):
        super().__init__(api, data)
        self.uri = f"job_templates/{self.id}"
        self.absolute_url = f"{self.api.base_url}execution/templates/job-template/{self.id}"

    def __str__(self):
        return f"JobTemplate(id={self.id}, name={self.name})"

    def jobs(self):
        jobs = self.api.retrieves_objects("jobs", baseuri=f"{self.uri}/jobs/",
                                          order_by="-finished", result_limit=50)
        return jobs

    def get_asked_variables(self):
        asked_vars = []
        for attr in dir(self):
            if attr.startswith('ask_') and getattr(self, attr) is True:
                asked_vars.append(attr[4:].replace('_on_launch', ''))
        return asked_vars

    def get_survey_spec(self):
        if not self.survey_enabled:
            return []
        response = self.api.get_request(f"{self.uri}/survey_spec/")
        if response is None or response.status_code != 200:
            return []
        survey_spec = response.json()
        return survey_spec.get('spec', [])

    def launch(self, payload=None):
        if payload is None:
            payload = {}

        response = self.api.post_request(f"{self.uri}/launch/", payload)
        return Job(self.api, response.json()) if response and response.status_code == 201 else None

class Inventory(BaseObject):
    def __init__(self, api, data):
        super().__init__(api, data)
        self.uri = f"inventories/{self.id}"
        self.absolute_url = f"{self.api.base_url}execution/infrastructure/inventories/inventory/{self.id}/details"

    def __str__(self):
        return f"Inventory(id={self.id}, name={self.name})"

    def get_hosts(self):
        response = self.api.get_request(f"{self.uri}/hosts/")

        if response is None or response.status_code != 200:
            self.log_error(response)
            return []

        hosts = []
        for item in response.json().get('results', []):
            hosts.append(Host(self.api, item))
        return hosts

class Host(BaseObject):
    def __init__(self, api, data):
        super().__init__(api, data)
        self.uri = f"inventory/{self.inventory}/hosts/{self.id}"
        self.absolute_url = f"{self.api.base_url}execution/infrastructure/inventories/inventory/{self.inventory}/hosts/{self.id}/details"

    def __str__(self):
        return f"Host(id={self.id}, name={self.name})"

class Project(BaseObject):
    def __init__(self, api, data):
        super().__init__(api, data)
        self.uri = f"projects/{self.id}"
        self.absolute_url = f"{self.api.base_url}execution/projects/{self.id}/details"

    def __str__(self):
        return f"Project(id={self.id}, name={self.name})"

    def sync(self):
        response = self.api.post_request(f"{self.uri}/update/", {})
        if response is None or response.status_code != 202:
            self.log_error(response)
            return False
        return True

class Job(BaseObject):
    def __init__(self, api, data):
        super().__init__(api, data)
        if not self.scm_branch:
            self.scm_branch = "main"
        self.uri = f"jobs/{self.id}"
        self.absolute_url = f"{self.api.base_url}execution/jobs/playbook/{self.id}/output"

    def __str__(self):
        return f"Job(id={self.id}, name={self.name}, status={self.status})"

    def print_stdout(self, follow=True):
        if follow:
            start_line = 0
            while True:
                self.refresh()
                stdout = self.get_stdout(start_line=start_line)
                if stdout:
                    start_line += len(stdout.splitlines())
                    print(stdout, end='')
                    if self.finished:
                        break
                time.sleep(5)
        else:
            stdout = self.get_stdout()
            if stdout is not None:
                print(stdout)

    def get_stdout(self, start_line=0):
        endpoint = f"{self.uri}/stdout/?format=json&start_line={start_line}"

        response = self.api.get_request(endpoint)

        if response is None or response.status_code != 200:
            return None

        return response.json().get('content', '')

    def relaunch(self):
        response = self.api.post_request(f"{self.uri}/relaunch/", {})
        return Job(self.api, response.json()) if response and response.status_code == 201 else None

    def cancel(self):
        response = self.api.post_request(f"{self.uri}/cancel/", {})
        if response is None or response.status_code != 202:
            self.log_error(response)
            return False
        return True
