#!/usr/bin/env python

import requests
import json
import urllib3
import time
from termcolor import colored
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class API(object):
    def __init__(self, baseurl, token):
        self.base_url = baseurl
        self.token = token
        self.api_path = "/api/v2/"
        if not self.base_url.endswith('/'):
            self.base_url += '/'
        self.url = f"{self.base_url}{self.api_path}"
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }

    def get_request(self, endpoint):
        try:
            response = requests.get(self.url + endpoint, headers=self.headers, verify=False)
            return response
        except requests.exceptions.RequestException as e:
            print(colored(f"Error connecting to API: {e}", 'red'))
            return None

    def post_request(self, endpoint, payload):
        try:
            response = requests.post(self.url + endpoint, headers=self.headers, json=payload, verify=False)
            return response
        except requests.exceptions.RequestException as e:
            print(colored(f"Error connecting to API: {e}", 'red'))
            return None

    def retrieves_objects(self, object_type, result_limit=10, order_by=None, baseuri=None, filters=None):
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
                url += f"&{key}={value}"

        print(url)
        response = self.get_request(url)
        if response is None or response.status_code != 200:
            print(colored(f"Error retrieving {object_type}: {response.status_code if response else 'No response'}", 'red'))
            return
        data = response.json().get('results', [])

        if not result_limit:
            result_limit = response.json().get('count', 0)

        while response.json().get('next') and len(data) < result_limit:
            endpoint = response.json().get('next').replace(self.api_path, '')
            response = self.get_request(endpoint)
            if response is None or response.status_code != 200:
                print(colored(f"Error retrieving {object_type}: {response.status_code if response else 'No response'}", 'red'))
                return
            for item in response.json().get('results', []):
                if len(data) < result_limit:
                    data.append(item)

        objects = [self.instantiate_object(object_type, item) for item in data]
        return objects

    def instantiate_object(self, object_type, data):
        if object_type == "inventories":
            return Inventory(self, data)
        elif object_type == "projects":
            return Project(self, data)
        elif object_type == "job_templates":
            return JobTemplate(self, data)
        elif object_type == "jobs":
            return Job(self, data)
        else:
            return None

class AAP(object):
    def __init__(self, api):
        self.api = api

    def get_inventories(self):
        return self.api.retrieves_objects("inventories", result_limit=0)

    def get_projects(self):
        return self.api.retrieves_objects("projects", result_limit=0)

    def get_job_templates(self):
        return self.api.retrieves_objects("job_templates", result_limit=0)

    def get_jobs(self, filters=None, result_limit=50):
        return list(reversed(self.api.retrieves_objects("jobs", result_limit=result_limit, order_by="-finished", filters=filters)))

    def get_job(self, job_id):
        response = self.api.get_request(f"jobs/{job_id}/")

        if response is None or response.status_code != 200:
            return

        return Job(self.api, response.json())

class BaseObject(object):
    def __init__(self, api, data):
        self.api = api
        self.init_vars(data)

    def init_vars(self, data):
        for k, v in data.items():
            setattr(self, k, v)
        self.data = data

class JobTemplate(BaseObject):
    def __init__(self, api, data):
        super().__init__(api, data)

    def __str__(self):
        return f"JobTemplate(id={self.id}, name={self.name})"

    def refresh(self):
        response = self.api.get_request(f"job_templates/{self.id}/")

        if response is None or response.status_code != 200:
            return
        self.__init__(self.api, response.json())

    def jobs(self):
        jobs = self.api.retrieves_objects("jobs", baseuri=f"job_templates/{self.id}/jobs/", order_by="-finished", result_limit=50)
        return jobs

    def get_asked_variables(self):
        asked_vars = []
        for attr in dir(self):
            if attr.startswith('ask_') and getattr(self, attr) is True:
                asked_vars.append(attr[4:].replace('_on_launch', ''))
        return asked_vars

    def launch(self, payload=None):
        if payload is None:
            payload = {}

        response = self.api.post_request(f"job_templates/{self.id}/launch/", payload)
        return Job(self.api, response.json()) if response and response.status_code == 201 else None

class Inventory(BaseObject):
    def __init__(self, api, data):
        super().__init__(api, data)

    def __str__(self):
        return f"Inventory(id={self.id}, name={self.name})"

    def refresh(self):
        response = self.api.get_request(f"inventories/{self.id}/")

        if response is None or response.status_code != 200:
            return
        self.init_vars(response.json())

    def get_hosts(self):
        response = self.api.get_request(f"inventories/{self.id}/hosts/")

        if response is None or response.status_code != 200:
            return

        hosts = []
        for item in response.json().get('results', []):
            hosts.append(Host(self.api, item))
        return hosts

class Host(BaseObject):
    def __init__(self, api, data):
        super().__init__(api, data)

    def __str__(self):
        return f"Host(id={self.id}, name={self.name})"

    def refresh(self):
        response = self.api.get_request(f"hosts/{self.id}/")

        if response is None or response.status_code != 200:
            return
        self.init_vars(response.json())

class Project(BaseObject):
    def __init__(self, api, data):
        super().__init__(api, data)

    def __str__(self):
        return f"Project(id={self.id}, name={self.name})"

    def refresh(self):
        response = self.api.get_request(f"projects/{self.id}/")

        if response is None or response.status_code != 200:
            return
        self.init_vars(response.json())

class Job(BaseObject):
    def __init__(self, api, data):
        super().__init__(api, data)
        if not self.scm_branch:
            self.scm_branch = "main"

    def __str__(self):
        return f"Job(id={self.id}, name={self.name}, status={self.status})"

    def refresh(self):
        response = self.api.get_request(f"jobs/{self.id}/")

        if response is None or response.status_code != 200:
            return
        self.init_vars(response.json())

    def print_stdout(self, follow=True):
        if follow:
            start_line = 0
            while True:
                self.refresh()
                stdout = self.get_stdout(start_line=start_line)
                start_line += len(stdout.splitlines())
                print(stdout, end='')
                if self.finished:
                    break
                time.sleep(2)
        else:
            stdout = self.get_stdout()
            if stdout is not None:
                print(stdout)

    def get_stdout(self, start_line=0):
        endpoint = f"jobs/{self.id}/stdout/?format=json&start_line={start_line}"

        response = self.api.get_request(endpoint)

        if response is None or response.status_code != 200:
            return

        return response.json().get('content', '')