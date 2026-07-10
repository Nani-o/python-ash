import io
import unittest
from collections import namedtuple
from contextlib import redirect_stdout
from collections import OrderedDict
from types import SimpleNamespace
from unittest.mock import Mock, call
from unittest.mock import patch

from ash.ash import Ash
from ash.commands import JT_COMMANDS, ROOT_COMMANDS
from ash.handlers.base import BaseHandler
from ash.handlers.root import RootHandler
from ash.handlers.job_template import JobTemplateHandler
from ash.handlers.job import JobHandler
from ash.handlers.inventory import InventoryHandler
from ash.handlers.project import ProjectHandler
from ash.object_types import PROJECTS, INVENTORIES, CACHED_OBJECT_TYPES


LIST_JOBS_COMMAND_LINE = "ls jobs project:demo nightly result_limit:5"


class BareAsh(Ash):
    def __init__(self):
        pass


class TestAshBehavior(unittest.TestCase):
    def setUp(self):
        self.ash = BareAsh()
        self.ash.display = Mock()
        self.ash.commands = ROOT_COMMANDS.copy()
        self.ash.completer = None
        self.ash._base_handler = BaseHandler(self.ash)
        self.ash._root_handler = RootHandler(self.ash)
        self.ash._jt_handler = JobTemplateHandler(self.ash)
        self.ash._job_handler = JobHandler(self.ash)
        self.ash._inventory_handler = InventoryHandler(self.ash)
        self.ash._project_handler = ProjectHandler(self.ash)
        self.ash._command_handlers = self.ash._build_command_handlers()

    def test_run_dispatches_known_command_with_args(self):
        self.ash.session = Mock()
        self.ash.session.prompt = Mock(side_effect=[LIST_JOBS_COMMAND_LINE, "exit"])
        self.ash.get_prompt = Mock(return_value=[])
        self.ash.aap = Mock()
        self.ash.aap.get_jobs.return_value = []
        self.ash.display_jobs = Mock()

        with redirect_stdout(io.StringIO()):
            self.ash.run()

        self.ash.aap.get_jobs.assert_called_once_with(
            filters={"project__search": ["demo"], "search": ["nightly"]},
            result_limit=5,
        )

    def test_get_objects_uses_cache_when_available(self):
        objects = [
            SimpleNamespace(id=1, name="Inventory A"),
            SimpleNamespace(id=2, name="Inventory B"),
        ]
        self.ash.cache = Mock()
        self.ash.cache.load_cache.return_value = objects
        self.ash.aap = Mock()

        with redirect_stdout(io.StringIO()):
            loaded, by_id, by_name = self.ash._get_objects(INVENTORIES)

        self.assertEqual(loaded, objects)
        self.assertEqual(by_id, {1: objects[0], 2: objects[1]})
        self.assertEqual(by_name, {"Inventory A": objects[0], "Inventory B": objects[1]})
        self.ash.aap.get_inventories.assert_not_called()
        self.ash.cache.insert_cache.assert_not_called()

    def test_get_objects_fetches_and_caches_when_cache_is_empty(self):
        objects = [
            SimpleNamespace(id=10, name="Project A"),
            SimpleNamespace(id=11, name="Project B"),
        ]
        self.ash.cache = Mock()
        self.ash.cache.load_cache.return_value = []
        self.ash.aap = Mock()
        self.ash.aap.get_projects.return_value = objects

        with redirect_stdout(io.StringIO()):
            loaded, by_id, by_name = self.ash._get_objects(PROJECTS)

        self.assertEqual(loaded, objects)
        self.assertEqual(by_id, {10: objects[0], 11: objects[1]})
        self.assertEqual(by_name, {"Project A": objects[0], "Project B": objects[1]})
        self.ash.aap.get_projects.assert_called_once_with()
        self.ash.cache.insert_cache.assert_has_calls(
            [call(PROJECTS, 10, objects[0]), call(PROJECTS, 11, objects[1])]
        )

    def test_filter_objects_supports_named_filters_and_plain_search(self):
        matching = SimpleNamespace(
            name="Deploy App",
            data={
                "summary_fields": {"project": {"name": "Core Platform"}},
                "project": "Core Platform",
            },
        )
        other = SimpleNamespace(
            name="Cleanup",
            data={
                "summary_fields": {"project": {"name": "Operations"}},
                "project": "Operations",
            },
        )
        filter_definitions = {"project": "Filter by project"}

        result = self.ash.filter_objects([matching, other], ["project:core", "deploy"], filter_definitions)

        self.assertEqual(result, [matching])

    def test_cmd_launch_merges_prompted_values_and_survey_vars(self):
        self.ash.commands = OrderedDict({**JT_COMMANDS, **ROOT_COMMANDS})
        self.ash.session = Mock()
        self.ash.session.prompt = Mock(side_effect=["launch", "exit"])
        self.ash.get_prompt = Mock(return_value=[])
        self.ash.session_wo_history = Mock()
        default_survey_input = ""
        launch_confirmation = "yes"
        self.ash.session_wo_history.prompt = Mock(
            side_effect=[default_survey_input, launch_confirmation]
        )
        self.ash.current_context = Mock()
        self.ash.current_context.get_asked_variables.return_value = ["inventory", "extra_vars"]
        self.ash.current_context.survey_enabled = True
        self.ash.current_context.get_survey_spec.return_value = [{
            "question_name": "Branch",
            "question_description": "Git branch to use",
            "variable": "branch",
            "required": False,
            "type": "text",
            "default": "main",
        }]

        launched_payloads = []

        def capture_launch(payload):
            launched_payloads.append(payload)

        self.ash.current_context.launch.side_effect = capture_launch

        prompted_values = {
            "inventory": ("inventory", 42),
            "extra_vars": ("extra_vars", {"env": "prod"}),
        }
        self.ash._ask_variable = Mock(side_effect=lambda var: prompted_values[var])
        self.ash.inventories_by_id = {}

        with redirect_stdout(io.StringIO()):
            self.ash.run()

        self.assertEqual(
            launched_payloads,
            [{"inventory": 42, "extra_vars": {"env": "prod", "branch": "main"}}],
        )

    def test_get_commands_for_context_returns_context_plus_root(self):
        commands = self.ash._get_commands_for_context(PROJECTS)

        self.assertIn("sync", commands)
        self.assertIn("cd", commands)
        self.assertEqual(commands["sync"], "project: Sync the selected project")

    def test_get_commands_for_unknown_context_returns_root_copy(self):
        commands = self.ash._get_commands_for_context("unknown_context")

        self.assertEqual(commands, ROOT_COMMANDS)
        self.assertIsNot(commands, ROOT_COMMANDS)

    def test_cd_project_uses_shared_cached_object_resolution(self):
        project = SimpleNamespace(id=42, name="Platform")
        self.ash.projects = [project]
        self.ash.projects_by_id = {42: project}
        self.ash._switch_context = Mock()

        self.ash._cd_project(["42"])

        self.ash._switch_context.assert_called_once_with(project, PROJECTS)

    def test_cd_inventory_not_found_displays_error(self):
        self.ash.inventories = []
        self.ash.inventories_by_id = {}

        self.ash._cd_inventory(["does-not-exist"])

        self.ash.display.print.assert_called_with("Inventory 'does-not-exist' not found.", 'red')

    def test_root_cache_with_invalid_type_prints_valid_types(self):
        self.ash.cache = Mock()
        self.ash._load_all_caches = Mock()

        self.ash._root_handler.cache(["invalid_type"])

        valid_types = ", ".join(CACHED_OBJECT_TYPES)
        self.ash.display.print.assert_called_with(
            f"Unknown cache type: invalid_type. Valid types are: {valid_types}.",
            'red',
        )
        self.ash.cache.clean_cache.assert_not_called()

    def test_root_cache_with_valid_type_refreshes_single_cache(self):
        self.ash.cache = Mock()
        self.ash._load_projects_cache = Mock()

        self.ash._root_handler.cache([PROJECTS])

        self.ash.cache.clean_cache.assert_called_once_with(PROJECTS)
        self.ash._load_projects_cache.assert_called_once_with()
        self.ash.display.print.assert_any_call("Cache refreshed.", 'green')

    def test_root_cache_without_args_refreshes_all_caches(self):
        self.ash.cache = Mock()
        self.ash._load_all_caches = Mock()

        self.ash._root_handler.cache([])

        self.ash.cache.clean_cache.assert_called_once_with()
        self.ash._load_all_caches.assert_called_once_with()
        self.ash.display.print.assert_any_call("Cache refreshed.", 'green')

    def test_ls_jobs_invalid_result_limit_does_not_query_api(self):
        self.ash.aap = Mock()

        self.ash._root_handler._ls_jobs(["result_limit:not_an_int"])

        self.ash.aap.get_jobs.assert_not_called()
        self.ash.display.print.assert_called_with("Invalid result_limit value. It should be an integer.", 'red')

    def test_watch_renders_description_on_last_line(self):
        terminal_size = namedtuple("TerminalSize", ["columns", "lines"])(80, 24)
        self.ash.api_description = "My AAP instance"
        self.ash.api_description_color = "green"
        self.ash.aap = Mock()
        self.ash.aap.get_jobs.return_value = []
        watch_args = ["project:demo", "nightly"]

        with patch("ash.handlers.root.get_terminal_size", return_value=terminal_size), \
             patch("ash.handlers.root.time.sleep", side_effect=KeyboardInterrupt):
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                with self.assertRaises(KeyboardInterrupt):
                    self.ash._root_handler.watch(watch_args)

        self.ash.aap.get_jobs.assert_called_once_with(
            filters={"project__search": ["demo"], "search": ["nightly"]},
            result_limit=22,
        )
        output = stdout.getvalue()
        self.assertIn("\033[?25l", output)
        self.assertIn("\033[?25h", output)
        self.assertIn("\033[24;1H\033[2K", output)
        self.assertIn("\033[24;22H", output)
        self.assertIn("[My AAP instance]", output)
        self.assertIn("project:demo nightly", output)
        self.assertIn("\033[32m", output)


if __name__ == "__main__":
    unittest.main()
