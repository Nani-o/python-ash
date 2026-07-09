#!/usr/bin/env python

"""Context management mixin for the Ash shell."""

from collections import OrderedDict

from .commands import (
    ROOT_COMMANDS,
    JT_COMMANDS,
    JOB_COMMANDS,
    INVENTORY_COMMANDS,
    PROJECT_COMMANDS,
)


class ContextMixin:
    """Mixin that manages the current context and prompt for the Ash shell."""

    def _switch_context(self, context, context_type):
        self.last_context = self.current_context
        self.last_context_type = self.current_context_type
        self.current_context = context
        self.current_context_type = context_type

        if context is not None:
            if context_type != 'jobs':
                context.refresh()
                self.cache.insert_cache(context_type, context.id, context)
            if context_type == 'job_templates':
                self.print(
                    f"Switched context to Job Template: ID={context.id}, Name={context.name}",
                    'cyan'
                )
            elif context_type == 'jobs':
                self.print(
                    f"Switched context to Job: ID={context.id}, Name={context.name}",
                    self.status_to_color(context.status)
                )
            elif context_type == 'inventories':
                self.print(
                    f"Switched context to Inventory: ID={context.id}, Name={context.name}",
                    'green'
                )
            elif context_type == 'projects':
                self.print(
                    f"Switched context to Project: ID={context.id}, Name={context.name}",
                    'orange'
                )
        else:
            self.print("Switched to root context", 'white')

        self.commands = self._get_commands_for_context(context_type)

    def _get_commands_for_context(self, context_type):
        if context_type == 'job_templates':
            return OrderedDict(list(JT_COMMANDS.items()) + list(ROOT_COMMANDS.items()))
        elif context_type == 'jobs':
            return OrderedDict(list(JOB_COMMANDS.items()) + list(ROOT_COMMANDS.items()))
        elif context_type == 'inventories':
            return OrderedDict(list(INVENTORY_COMMANDS.items()) + list(ROOT_COMMANDS.items()))
        elif context_type == 'projects':
            return OrderedDict(list(PROJECT_COMMANDS.items()) + list(ROOT_COMMANDS.items()))
        else:
            return ROOT_COMMANDS.copy()

    def get_prompt(self):
        prompt = [('class:white', 'ash ')]
        if self.api_description:
            prompt.append((f'class:{self.api_description_color}', f'[{self.api_description}] '))
        if self.current_context:
            context_type = self.current_context_type
            if context_type == 'job_templates':
                label = (
                    f"JobTemplate[{self.current_context.id}] - "
                    f"{self.current_context.name} "
                )
                prompt.append(('class:cyan', label))
            elif context_type == 'jobs':
                color = self.status_to_color(self.current_context.status)
                label = (
                    f"Job[{self.current_context.id}] - "
                    f"{self.current_context.name} - "
                    f"{self.current_context.status} "
                )
                prompt.append((f'class:{color}', label))
            elif context_type == 'inventories':
                label = (
                    f"Inventory[{self.current_context.id}] - "
                    f"{self.current_context.name} "
                )
                prompt.append(('class:green', label))
            elif context_type == 'projects':
                label = (
                    f"Project[{self.current_context.id}] - "
                    f"{self.current_context.name} "
                )
                prompt.append(('class:orange', label))
        prompt.append(('class:white', '> '))
        return prompt
