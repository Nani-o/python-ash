#!/usr/bin/env python

"""Inventory context command handler."""

from .base import BaseHandler


class InventoryHandler(BaseHandler):
    """Handles commands available in the inventory context: hosts, add_hosts, clear_hosts."""

    def hosts(self, args):
        ash = self.ash
        hosts = ash.current_context.get_hosts()
        if hosts:
            for host in hosts:
                print(f"{host.id}: {host.name}")
        else:
            print("No hosts found in this inventory.")

    def add_hosts(self, args):
        ash = self.ash
        ash.display.print("(Multi-line input enabled. Use Meta+Enter or Escape followed by Enter to finish input)", 'yellow')
        prompt = "Hosts to add (one per line):\n"

        user_input = ash.session_wo_history.prompt(prompt, multiline=True)
        results = ash.current_context.add_hosts(user_input.splitlines())

        for host, result in results.items():
            if result is not None:
                if result.status_code in [201]:
                    ash.display.print(f"{host}: Host added successfully.", 'green')
                elif result.status_code == 400:
                    ash.display.print(f"{host}: {result.json().get('__all__', ['Unknown error'])[0]}", 'red')
                else:
                    ash.display.print(f"{host}: Failed to add host. Status code: {result.status_code}", 'red')

    def clear_hosts(self, args):
        ash = self.ash
        confirmation = ash.session_wo_history.prompt("Are you sure you want to delete all hosts from this inventory? This action cannot be undone. [no]: ", multiline=False) or "no"
        if confirmation.lower() in ['yes', 'y']:
            results = ash.current_context.clear_hosts()
            for host, result in results.items():
                if result is not None:
                    if result.status_code in [204]:
                        ash.display.print(f"{host}: Host deleted successfully.", 'green')
                    else:
                        ash.display.print(f"{host}: Failed to delete host. Status code: {result.status_code}", 'red')
        else:
            ash.display.print("Operation cancelled.", 'yellow')
