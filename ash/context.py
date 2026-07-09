#!/usr/bin/env python

"""Context management mixin for the Ash shell."""

from collections import OrderedDict

from .types import ContextType
from .commands import (
    ROOT_COMMANDS,
    JT_COMMANDS,
    JOB_COMMANDS,
    INVENTORY_COMMANDS,
    PROJECT_COMMANDS,
)


# Per-context-type configuration: colour, human label, command set, and
# the short token used in the prompt line.
_CONTEXT_TYPE_CONFIG = {
    ContextType.JOB_TEMPLATES: {
        'color': 'cyan',
        'label': 'Job Template',
        'commands': JT_COMMANDS,
        'prompt_label': 'JobTemplate',
    },
    ContextType.JOBS: {
        'color': None,          # determined at runtime by job.status
        'label': 'Job',
        'commands': JOB_COMMANDS,
        'prompt_label': 'Job',
    },
    ContextType.INVENTORIES: {
        'color': 'green',
        'label': 'Inventory',
        'commands': INVENTORY_COMMANDS,
        'prompt_label': 'Inventory',
    },
    ContextType.PROJECTS: {
        'color': 'orange',
        'label': 'Project',
        'commands': PROJECT_COMMANDS,
        'prompt_label': 'Project',
    },
}


class ContextMixin:
    """Mixin that manages the current context and prompt for the Ash shell."""

    def _switch_context(self, context, context_type):
        self.last_context = self.current_context
        self.last_context_type = self.current_context_type
        self.current_context = context
        self.current_context_type = context_type

        if context is not None:
            if context_type != ContextType.JOBS:
                context.refresh()
                self.cache.insert_cache(context_type, context.id, context)
            cfg = _CONTEXT_TYPE_CONFIG[ContextType(context_type)]
            color = cfg['color'] or self.status_to_color(context.status)
            self.print(
                f"Switched context to {cfg['label']}: ID={context.id}, Name={context.name}",
                color
            )
        else:
            self.print("Switched to root context", 'white')

        self.commands = self._get_commands_for_context(context_type)

    def _get_commands_for_context(self, context_type):
        if context_type is None:
            return ROOT_COMMANDS.copy()
        cfg = _CONTEXT_TYPE_CONFIG.get(ContextType(context_type))
        if cfg:
            return OrderedDict(list(cfg['commands'].items()) + list(ROOT_COMMANDS.items()))
        return ROOT_COMMANDS.copy()

    def get_prompt(self):
        prompt = [('class:white', 'ash ')]
        if self.api_description:
            prompt.append((f'class:{self.api_description_color}', f'[{self.api_description}] '))
        if self.current_context:
            cfg = _CONTEXT_TYPE_CONFIG.get(ContextType(self.current_context_type))
            if cfg:
                if self.current_context_type == ContextType.JOBS:
                    color = self.status_to_color(self.current_context.status)
                    label = (
                        f"Job[{self.current_context.id}] - "
                        f"{self.current_context.name} - "
                        f"{self.current_context.status} "
                    )
                else:
                    color = cfg['color']
                    label = (
                        f"{cfg['prompt_label']}[{self.current_context.id}] - "
                        f"{self.current_context.name} "
                    )
                prompt.append((f'class:{color}', label))
        prompt.append(('class:white', '> '))
        return prompt
