#!/usr/bin/env python

"""Display mixin providing all rendering and formatting logic for Ash."""

import re

import dateutil.parser
from prompt_toolkit import print_formatted_text
from prompt_toolkit.formatted_text import FormattedText

from .models import JobTemplate, Inventory, Project, Job


# Maps job status values to their display colour.
_STATUS_COLORS = {
    'successful': 'blue',
    'failed': 'red',
    'error': 'red',
    'canceled': 'magenta',
    'pending': 'yellow',
    'waiting': 'yellow',
    'running': 'yellow',
}

# Maps model class to a fixed display colour; Job uses status_to_color instead.
_OBJECT_TYPE_COLORS = {
    JobTemplate: 'cyan',
    Inventory: 'green',
    Project: 'orange',
    Job: None,
}

_ISO_DATETIME_RE = re.compile(
    r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}"
    r"(\.[0-9]+)?([Zz]|([\+-])([01]\d|2[0-3]):?([0-5]\d)?)?"
)


class DisplayMixin:
    """Mixin that provides print / display helpers to the Ash shell."""

    def print(self, message, class_name=None, attrs=None, end='\n'):
        if class_name:
            print_formatted_text(
                FormattedText([(f'class:{class_name}', message)]),
                style=self.style, end=end
            )
        else:
            print(message, end=end)

    def status_to_color(self, status):
        return _STATUS_COLORS.get(status, 'white')

    def object_to_color(self, obj):
        for cls, color in _OBJECT_TYPE_COLORS.items():
            if isinstance(obj, cls):
                return color if color is not None else self.status_to_color(obj.status)
        return 'white'

    def parse_label(self, label, max_length=None):
        if _ISO_DATETIME_RE.match(label):
            try:
                dt = dateutil.parser.isoparse(label)
                label = dt.astimezone().strftime('%d/%m-%H:%M')
            except (ValueError, TypeError):
                pass
        if max_length is None or len(label) <= max_length:
            return label
        return label[:max_length - 3] + '...'

    def display_jobs(self, jobs):
        self.display_by_columns(
            jobs, ['id', 'created', 'limit', 'name', 'playbook', 'scm_branch', 'status']
        )

    def display_job_templates(self, job_templates):
        self.display_by_columns(job_templates, ['id', 'name', 'playbook'])

    def display_inventories(self, inventories):
        self.display_by_columns(inventories, ['id', 'name', 'total_hosts'])

    def display_projects(self, projects):
        self.display_by_columns(projects, ['id', 'name', 'scm_url'])

    def display_by_columns(self, objects, columns):
        column_widths = {}
        for col in columns:
            if col in ('created', 'modified', 'finished'):
                max_len = 11
            else:
                max_len = max(
                    [len(str(getattr(obj, col))) for obj in objects] + [len(col)]
                )
            if col == 'limit' and max_len > 30:
                max_len = 30
            elif col == 'scm_branch' and max_len > 25:
                max_len = 25
            column_widths[col] = max_len

        format_str = "   ".join([f"{{:<{column_widths[col]}}}" for col in columns])
        self.print(format_str.format(*columns), 'headers')
        for obj in objects:
            message = format_str.format(
                *[self.parse_label(str(getattr(obj, col)), column_widths[col]) for col in columns]
            )
            self.print(message, self.object_to_color(obj) + '_bold')
