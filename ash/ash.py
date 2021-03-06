#!/usr/bin/env python

"""
Ash class file

"""
from .cli import Cli
from .execution import Execution
from .completer import AnsibleCompleter
from .configuration import Config
from .configuration import CONFIGS_DEF
from .helper import AnsibleHelper
from .helper import AnsibleCommand

try:
    from collections import OrderedDict
except ImportError:
    from ordereddict import OrderedDict
import os
import sys
import shlex
import tempfile
import textwrap
from contextlib import contextmanager

ROOT_COMMANDS = OrderedDict([
    ('args', 'Command line arguments to pass'),
    ('exit', 'Quit program'),
    ('extra-vars', 'Set extra variables for the command line'),
    ('forks', 'Set number of parrallel ansible processes'),
    ('list', 'List hosts targeted/in group/in inventory'),
    ('module', 'Choose a module to use'),
    ('play', 'Execute playbook or module on target'),
    ('playbook', 'Choose a playbook to use'),
    ('set', 'Set configurations in-memory'),
    ('reset', 'Remove all arguments set'),
    ('shellmode', 'Enter shell commands directly on target'),
    ('target', 'Target an Ansible host or group')
])

LIST_COMMANDS = OrderedDict([
    ('hosts', 'List all hosts from inventory'),
    ('groups', 'List all groups from inventory'),
    ('target', 'List all targeted hosts'),
    ('tasks', 'List all tasks that would be executed'),
    ('tags', 'List all tags of a playbooks')
])


class Ash(object):

    """
    This class is aimed to prompt the user for the various ash commands,
    store the different parameters supplied and execute it accordingly
    """

    def __init__(self):
        self.hosts = None
        self.method = None
        self.action = None
        self.module_args = None
        self.arguments = None
        self.extra_cli = {}
        self.execution = Execution()
        self.config = Config()
        self.commands = ROOT_COMMANDS.keys()
        self.config_definitions = CONFIGS_DEF
        try:
            self.editor = os.environ['EDITOR']
        except KeyError:
            self.editor = "/usr/bin/vi"
        self.buffer = None
        self.is_shellmode = False

        self.ansible_helper = AnsibleHelper()
        self.inventory = self.ansible_helper.inventory

        self.completer = AnsibleCompleter(
            self.inventory, ROOT_COMMANDS, LIST_COMMANDS,
            self.config_definitions, self.config
        )
        self.cli = Cli(self.get_prompt(), self.completer)

    def get_prompt(self):
        """Return the prompt to show to the user"""
        prompt = []
        prompt.append(('ash ', 'white'))

        if self.hosts:
            prompt.append(("[" + self.hosts + "] ", 'cyan'))

        if self.is_shellmode:
            prompt.append(('shellmode ', 'red'))
        else:
            if self.method == "module":
                segment = self.method[0] + ":" + self.action + " "
                prompt.append((segment, 'yellow'))
            if self.method == "playbook":
                if len(self.action) > 1:
                    playbooks_list = [x.split('/')[-1] for x in self.action]
                    playbooks = ','.join(playbooks_list)
                else:
                    playbooks = self.action[0]
                segment = self.method[0] + ":" + playbooks + " "
                prompt.append((segment, 'yellow'))
            if self.arguments:
                prompt.append(("a:ok ", 'red'))

        prompt.append(("> ", 'white'))
        return prompt

    def target(self):
        """Set the hosts to target"""
        if not self.buffer:
            message = "Argument missing"
            self.cli.show_message(message, "red")
            return

        hosts = [x.name for x in self.inventory.list_hosts(self.buffer)]

        if len(hosts) != 0:
            message = '{} hosts matched'.format(str(len(hosts)))
            color = "green"
            self.hosts = self.buffer
        else:
            message = "No hosts matched"
            color = "red"
        self.cli.show_message(message, color)

    def module(self):
        """Set the module to use"""
        if not self.buffer:
            print("Argument missing")
            return
        self.method = "module"
        module_name = self.buffer.split()[0]
        module_args = ' '.join(self.buffer.split()[1:])
        self.action = module_name
        self.module_args = module_args

    def playbook(self):
        """Set the playbook to play"""
        if not self.buffer:
            print("Argument missing")
            return
        self.method = "playbook"
        self.action = shlex.split(self.buffer)
        self.module_args = None

    def forks(self):
        """Set the forks parameter of ansible"""
        if not self.buffer:
            print("Argument missing")
            return
        self.extra_cli["forks"] = shlex.split(self.buffer)[0]

    def extra_vars(self):
        """Set extra vars to be used for the play"""
        if not self.buffer:
            print("Argument missing")
            return
        self.extra_cli["extra-vars"] = self.buffer

    def args(self):
        """Set arguments to be passed to the ansible command line"""
        if not self.buffer:
            print("Argument missing")
            return
        self.arguments = shlex.split(self.buffer)

#    def config(self):
#        """Set the path to the ansible.cfg to use"""
#        if not self.buffer:
#            print("Argument missing")
#            return
#        self. = shlex.split(self.buffer)

    def play(self):
        """Play ansible run based on the parameters supplied"""
        if not self.method:
            message = "Please select a module or playbook to use"
            self.cli.show_message(message, "red")
            return
        if self.method == "module" and not self.hosts:
            message = "Please select a target"
            self.cli.show_message(message, "red")
            return

        command = self.get_command()

        message = 'Executing : {}'.format(command.printable_command)
        self.cli.show_message(message, "white")

        self.execution.execute_command(command.executable_command, True)

    def get_command(self):
        """Return the command generated"""
        command = AnsibleCommand(
            self.method, self.action, hosts=self.hosts, module_args=self.module_args,
            forks=self.extra_cli["forks"], extra_vars=self.extra_cli["extra_vars"],
            extra_args=self.arguments
        )
        return command

    def set(self):
        """Set configurations in-memory or permanently"""
        if not self.buffer:
            print("Argument missing")
            return
        elif self.buffer not in self.config_definitions.keys():
            print(self.buffer + " is not a configuration variable")
            return

        edit_file_path = self.configuration_tempfile_with_example(self.buffer)
        command = [self.editor, edit_file_path]

        self.execution.execute_command(command, True)

        new_value = self.config.get_variable_from_file(self.buffer,
                                                       edit_file_path)
        type_to_check = self.config_definitions[self.buffer]["type"]
        if new_value is not None and isinstance(new_value, type_to_check):
            self.config.configurations[self.buffer] = new_value
            print(self.buffer + " modified")
        else:
            print(self.buffer + " unmodified")

        os.remove(edit_file_path)

    def configuration_tempfile_with_example(self, variable):
        """Return the path of a tempfile loaded with a commented configuration
        example
        """
        file, temp_file_path = tempfile.mkstemp(prefix="ash-")

        content = '{}:\n\n'.format(variable)
        content += '# Example : \n'
        example = self.config_definitions[variable]["example"]
        for line in textwrap.dedent(example).split('\n'):
            content += '#    {}\n'.format(line)

        with open(temp_file_path, "w") as temp_file:
            temp_file.write(content)

        return temp_file_path

    def list(self):
        """List groups and hosts"""
        if not self.buffer or self.buffer == "target":
            if self.method == "playbook":
                self.save_context()
                self.arguments = ["--list-hosts"]
                self.play()
                self.restore_context()
                return
            elif self.hosts:
                list = [x.name for x in self.inventory.list_hosts(self.hosts)]
            else:
                print("No hosts targeted")
                return
        elif self.buffer == "hosts":
            list = [x.name for x in self.inventory.list_hosts()]
        elif self.buffer == "groups":
            list = self.inventory.list_groups()
        elif self.buffer == "tasks" or self.buffer == "tags":
            if self.method and self.action:
                if self.method == "playbook":
                    self.save_context()
                    self.arguments = ["--list-" + self.buffer]
                    self.buffer = None
                    self.play()
                    self.restore_context()
                else:
                    print("No such option for modules")
            else:
                print("You must select a target and a playbook")
            return
        elif self.buffer in self.inventory.list_groups():
            list = [x.name for x in self.inventory.list_hosts(self.buffer)]
        else:
            print("Not such option : " + self.buffer)
            return

        print('\n'.join(list))

    def reset(self):
        """Reset all parameters to None"""
        self.hosts = None
        self.method = None
        self.action = None
        self.module_args = None
        self.arguments = None
        self.extra_cli = {}

    def save_context(self):
        self.context = (
            self.method, self.action,
            self.module_args, self.arguments
        )

    def restore_context(self):
        (self.method,
         self.action,
         self.module_args,
         self.arguments) = self.context

    def shellmode(self):
        if not self.is_shellmode and self.hosts:
            self.save_context()
            self.is_shellmode = True
        elif self.is_shellmode:
            self.is_shellmode = False
            self.restore_context()
        else:
            message = "Select target before using shellmode"
            self.cli.show_message(message, "red")

    def exec_shellmode(self, command):
        if command == "shellmode":
            self.shellmode()
        else:
            self.method = "module"
            self.action = "shell"
            self.module_args = command
            self.arguments = None
            self.play()

    def exec_command(self, command):
        if command.strip() == "":
            return
        if self.is_shellmode:
            self.exec_shellmode(command)
        else:
            root_command = command.split(' ')[0]
            self.buffer = ' '.join(command.split(' ')[1:])

            if root_command in self.commands:
                root_command = root_command.replace('-', '_')
                func = getattr(self, root_command)
                func()
            else:
                self.cli.show_message("Command not found", "red")

    def exit(self):
        self.cli.exit()

    def run(self):
        """Prompt user for a command and execute the input accordingly"""
        self.buffer = None
        result = self.cli.show_prompt().lstrip(' ').rstrip(' ')

        self.exec_command(result)

        self.cli.prompt = self.get_prompt()
