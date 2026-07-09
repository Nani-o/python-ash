#!/usr/bin/env python

"""Low-level HTTP client for the Ansible Automation Platform API."""

import requests
from termcolor import colored

import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class API:
    def __init__(self, baseurl, token, api_path):
        self.base_url = baseurl
        self.token = token
        self.api_path = api_path
        self.url = requests.compat.urljoin(self.base_url, self.api_path)
        self.headers = {
            "Authorization": "Bearer " + self.token,
            "Content-Type": "application/json"
        }

    def get_request(self, endpoint):
        try:
            response = requests.get(
                requests.compat.urljoin(self.url, endpoint),
                headers=self.headers, verify=False, timeout=10
            )
            return response
        except requests.exceptions.RequestException as e:
            print(colored(f"Error connecting to API: {e}", 'red'))
            return None

    def post_request(self, endpoint, payload):
        try:
            response = requests.post(
                requests.compat.urljoin(self.url, endpoint),
                headers=self.headers, json=payload, verify=False, timeout=10
            )
            return response
        except requests.exceptions.RequestException as e:
            print(colored(f"Error connecting to API: {e}", 'red'))
            return None

    def delete_request(self, endpoint):
        try:
            response = requests.delete(
                requests.compat.urljoin(self.url, endpoint),
                headers=self.headers, verify=False, timeout=10
            )
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

        return [self.instantiate_object(object_type, item) for item in data]

    def instantiate_object(self, object_type, data):
        from .models import OBJECT_REGISTRY
        cls = OBJECT_REGISTRY.get(object_type)
        return cls(self, data) if cls else None

    def log_error(self, response):
        if response is None:
            print(colored("Error: No response from API", 'red'))
        else:
            print(colored(f"Error: {response.status_code} - {response.text}", 'red'))
