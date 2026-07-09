#!/usr/bin/env python

"""Display and formatting utilities for ash."""

import re

import dateutil.parser
from prompt_toolkit import print_formatted_text
from prompt_toolkit.formatted_text import FormattedText

from .models import Inventory, Job, JobTemplate, Project


class Display:
    def __init__(self, style):
        self.style = style

    def print(self, message, class_name=None, attrs=None, end='\n'):
        if class_name:
            print_formatted_text(FormattedText([(f'class:{class_name}', message)]), style=self.style, end=end)
        else:
            print(message, end=end)

    def parse_label(self, label, max_length=None):
        # if string is ISO datetime, parse and format it
        if re.match(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(\.[0-9]+)?([Zz]|([\+-])([01]\d|2[0-3]):?([0-5]\d)?)?", label):
           try:
                dt = dateutil.parser.isoparse(label)
                label = dt.astimezone().strftime('%d/%m-%H:%M')
           except (ValueError, TypeError):
                pass
        if max_length is None or len(label) <= max_length:
            return label
        else:
            return label[:max_length-3] + '...'

    def status_to_color(self, status):
        if status == 'successful':
            return 'blue'
        elif status in ['failed', 'error']:
            return 'red'
        elif status == 'canceled':
            return 'magenta'
        elif status in ['pending', 'waiting', 'running']:
            return 'yellow'
        else:
            return 'white'

    def object_to_color(self, obj):
        if isinstance(obj, JobTemplate):
            return 'cyan'
        elif isinstance(obj, Inventory):
            return 'green'
        elif isinstance(obj, Project):
            return 'orange'
        elif isinstance(obj, Job):
            return self.status_to_color(obj.status)
        else:
            return 'white'

    def display_by_columns(self, objects, columns):
        column_widths = {}
        for col in columns:
            if col in ['created', 'modified', 'finished']:
                max_len = 11
            else:
                max_len = max([len(str(getattr(obj, col))) for obj in objects] + [len(col)])
            if col == 'limit' and max_len > 30:
                max_len = 30
            elif col == 'scm_branch' and max_len > 25:
                max_len = 25
            column_widths[col] = max_len

        format_str = "   ".join([f"{{:<{column_widths[col]}}}" for col in columns])
        header = format_str.format(*[col for col in columns])
        self.print(header, 'headers')
        for obj in objects:
            message = format_str.format(*[self.parse_label(str(getattr(obj, col)), column_widths[col]) for col in columns])
            color = self.object_to_color(obj)
            self.print(message, color + '_bold')

    def display_jobs(self, jobs):
        self.display_by_columns(jobs, ['id', 'created', 'limit', 'name', 'playbook', 'scm_branch', 'status'])

    def display_job_templates(self, job_templates):
        self.display_by_columns(job_templates, ['id', 'name', 'playbook'])

    def display_inventories(self, inventories):
        self.display_by_columns(inventories, ['id', 'name', 'total_hosts'])

    def display_projects(self, projects):
        self.display_by_columns(projects, ['id', 'name', 'scm_url'])
