#!/usr/bin/env python

"""Root-level command handlers: ls, cd, watch, cache."""

import sys
import time
from os import get_terminal_size

from .base import BaseHandler
from ..commands import (
    CD_COMMANDS, LS_COMMANDS, LS_JOB_TEMPLATE_FILTERS,
    LS_INVENTORIES_FILTERS, LS_PROJECTS_FILTERS, LS_JOBS_FILTERS,
)
from ..object_types import CACHED_OBJECT_TYPES


class RootHandler(BaseHandler):
    """Handles ls, cd, watch, and cache commands."""

    # ------------------------------------------------------------------ #
    # ls
    # ------------------------------------------------------------------ #

    def ls(self, args):
        ash = self.ash
        if len(args) == 0:
            ash.display.print("Usage: ls <object_type>", 'yellow')
            return

        object_type = args[0]

        if object_type not in LS_COMMANDS.keys():
            ash.display.print(f"Unknown object type: {object_type}", 'red')
            return

        method = getattr(self, f'_ls_{object_type}', None)
        method(args[1:])

    def _ls_job_templates(self, args):
        ash = self.ash
        if not ash.job_templates:
            ash.display.print("No job templates in cache. Try using 'cache' command.", 'yellow')
            return

        job_templates = ash.filter_objects(ash.job_templates, args, LS_JOB_TEMPLATE_FILTERS)
        ash.display.display_job_templates(job_templates)

    def _ls_jobs(self, args):
        ash = self.ash
        filters, result_limit = self._parse_ls_jobs_args(args)
        if filters is None and result_limit is None:
            return
        jobs = ash.aap.get_jobs(filters=filters, result_limit=result_limit)
        if jobs:
            ash.display.display_jobs(jobs)
        else:
            ash.display.print("No jobs found.", 'yellow')

    def _ls_inventories(self, args):
        ash = self.ash
        if not ash.inventories:
            ash.display.print("No inventories in cache. Try using 'cache' command.", 'yellow')
            return

        inventories = ash.filter_objects(ash.inventories, args, LS_INVENTORIES_FILTERS)
        ash.display.display_inventories(inventories)

    def _ls_projects(self, args):
        ash = self.ash
        if not ash.projects:
            ash.display.print("No projects in cache. Try using 'cache' command.", 'yellow')
            return

        projects = ash.filter_objects(ash.projects, args, LS_PROJECTS_FILTERS)
        ash.display.display_projects(projects)

    def _parse_ls_jobs_args(self, args):
        ash = self.ash
        result_limit = 100
        filters = {}
        for arg in [a.lower() for a in args]:
            if ':' in arg and arg.split(':', 1)[0] in LS_JOBS_FILTERS.keys():
                filter_key, filter_value = arg.split(':', 1)
                if filter_key == 'result_limit':
                    try:
                        filter_value = int(filter_value)
                    except ValueError:
                        ash.display.print("Invalid result_limit value. It should be an integer.", 'red')
                        return None, None
                    result_limit = filter_value
                    continue
                filter_key = f"{filter_key}__search"
            else:
                filter_key = "search"
                filter_value = arg

            if filter_key in filters:
                filters[filter_key].append(filter_value)
            else:
                filters[filter_key] = [filter_value]
        return filters, result_limit

    # ------------------------------------------------------------------ #
    # watch
    # ------------------------------------------------------------------ #

    def watch(self, args):
        ash = self.ash
        while True:
            result_limit = get_terminal_size().lines - 2
            filters, _ = self._parse_ls_jobs_args(args)
            if filters is None:
                return
            jobs = ash.aap.get_jobs(filters=filters, result_limit=result_limit)
            # Move cursor to the beginning of the first line and clear to the end of the screen
            sys.stdout.write('\033[H')  # Move cursor to the top-left corner
            sys.stdout.write('\033[J')  # Clear from cursor to the end of the screen
            sys.stdout.flush()
            if jobs:
                ash.display.display_jobs(jobs)
            time.sleep(5)

    # ------------------------------------------------------------------ #
    # cache
    # ------------------------------------------------------------------ #

    def cache(self, args):
        ash = self.ash
        if args:
            valid_cache_types = ", ".join(CACHED_OBJECT_TYPES)
            if args[0] not in CACHED_OBJECT_TYPES:
                ash.display.print(f"Unknown cache type: {args[0]}. Valid types are: {valid_cache_types}.", 'red')
                return
            ash.cache.clean_cache(args[0])
            method = getattr(ash, f'_load_{args[0]}_cache', None)
            method()
        else:
            ash.cache.clean_cache()
            ash._load_all_caches()
        ash.display.print("Cache refreshed.", 'green')

    # ------------------------------------------------------------------ #
    # cd
    # ------------------------------------------------------------------ #

    def cd(self, args):
        ash = self.ash
        if len(args) == 0:
            ash._switch_context(None, None)
            return
        elif len(args) < 2:
            if args[0] == '-':
                if ash.last_context:
                    ash._switch_context(ash.last_context, ash.last_context_type)
                else:
                    ash.display.print("No previous context to switch back to.", 'red')
            else:
                ash.display.print("Usage: cd <object_type> <name_or_id>", 'red')
            return

        object_type = args[0]

        if object_type not in CD_COMMANDS.keys():
            ash.display.print(f"Unknown object type: {object_type}", 'red')
            return

        method = getattr(ash, f'_cd_{object_type}', None)
        method(args[1:])
