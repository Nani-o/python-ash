#!/usr/bin/env python

"""Domain model classes for Ansible Automation Platform objects."""

import time

import requests
from termcolor import colored


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
        self.absolute_url = requests.compat.urljoin(self.api.base_url, f"execution/templates/job-template/{self.id}")

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
                var = attr[4:].replace('_on_launch', '')
                if var == 'variables':
                    var = 'extra_vars'
                elif var == 'tags':
                    var = 'job_tags'
                asked_vars.append(var)
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
        self.absolute_url = requests.compat.urljoin(self.api.base_url, f"execution/infrastructure/inventories/inventory/{self.id}/details")

    def __str__(self):
        return f"Inventory(id={self.id}, name={self.name})"

    def get_hosts(self):
        return self.api.retrieves_objects("hosts", baseuri=f"{self.uri}/hosts/", result_limit=0)

    def add_hosts(self, hosts):
        results = {}
        for host in hosts:
            payload = {
                "description": "Added using ash command line",
                "enabled": True,
                "name": host
                # "variables": "string"
            }
            result = self.api.post_request(f"{self.uri}/hosts/", payload)
            results[host] = result
        return results

    def clear_hosts(self):
        hosts = self.get_hosts()
        results = {}
        for host in hosts:
            result = self.api.get_request(f"hosts/{host.id}/")
            if result is not None and result.status_code == 200:
                delete_result = self.api.delete_request(f"hosts/{host.id}")
                results[host.name] = delete_result
            else:
                results[host.name] = result
        return results


class Host(BaseObject):
    def __init__(self, api, data):
        super().__init__(api, data)
        self.uri = f"inventory/{self.inventory}/hosts/{self.id}"
        self.absolute_url = requests.compat.urljoin(self.api.base_url, f"execution/infrastructure/inventories/inventory/{self.inventory}/hosts/{self.id}/details")

    def __str__(self):
        return f"Host(id={self.id}, name={self.name})"


class Project(BaseObject):
    def __init__(self, api, data):
        super().__init__(api, data)
        self.uri = f"projects/{self.id}"
        self.absolute_url = requests.compat.urljoin(self.api.base_url, f"execution/projects/{self.id}/details")

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
        self.uri = f"jobs/{self.id}"
        self.absolute_url = requests.compat.urljoin(self.api.base_url, f"execution/jobs/playbook/{self.id}/output")

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
