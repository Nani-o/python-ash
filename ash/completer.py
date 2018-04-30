#!/usr/bin/env python

from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.completion import Completer, Completion

import re
import json
import os

from collections import OrderedDict

class AshCompleter(Completer):
    def __init__(self, ash_instance):
        self.ash = ash_instance

    def _match_input(self, input, struct):
        if isinstance(struct, dict):
            result = OrderedDict(
                (key, value) for key, value
                in struct.items()
                if key.startswith(input))
        elif isinstance(struct, list) or isinstance(struct, set):
            result = [x for x in struct if x.startswith(input)]
        return result

    def get_completions(self, document, complete_event):
        self.cur_text = document.text_before_cursor
        self.cur_word = document.get_word_before_cursor(WORD=True)
        self.word_list = self.cur_text.split(' ')
        self.completions = []

        if len(self.word_list) == 1:
            self.completions = self._match_input(self.cur_word, self.ash.commands)
        else:
            command = self.word_list[0]
            if command == "ls":
                if len(self.word_list) == 2:
                    self.completions = self._match_input(
                        self.cur_word,
                        self.ash.ls_commands
                    )
                elif len(self.word_list) >= 3:
                    subcommand = self.word_list[1]
                    if subcommand in self.ash.ls_commands_filters:
                        filters = {key + ':': value for key,value in self.ash.ls_commands_filters[subcommand].items()}
                        self.completions = self._match_input(
                            self.cur_word,
                            filters
                        )
            elif command == "cd":
                if len(self.word_list) == 2:
                    self.completions = self._match_input(
                        self.cur_word,
                        self.ash.cd_commands
                    )
                elif len(self.word_list) == 3:
                    subcommand = self.word_list[1]
                    if subcommand == "project":
                        project_names = list(self.ash.projects_by_name.keys())
                        self.completions = self._match_input(
                            self.cur_word,
                            project_names
                        )
                    elif subcommand == "inventory":
                        inventory_names = list(self.ash.inventories_by_name.keys())
                        self.completions = self._match_input(
                            self.cur_word,
                            inventory_names
                        )
                    elif subcommand == "job_template":
                        jt_names = list(self.ash.job_templates_by_name.keys())
                        self.completions = self._match_input(
                            self.cur_word,
                            jt_names
                        )

        if isinstance(self.completions, list):
            self.completions.sort()

        for word in self.completions:
            if isinstance(self.completions, dict):
                meta = self.completions[word]
            else:
                meta = None

            yield Completion(word, -len(self.cur_word), display_meta=meta)
