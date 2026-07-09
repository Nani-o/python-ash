#!/usr/bin/env python

"""Project context command handler."""

from .base import BaseHandler


class ProjectHandler(BaseHandler):
    """Handles commands available in the project context: sync."""

    def sync(self, args):
        project = self.ash.current_context
        project.sync()
        print(f"Project '{project.name}' sync initiated.")
