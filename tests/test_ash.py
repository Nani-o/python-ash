import io
import unittest
from contextlib import redirect_stdout
from collections import OrderedDict
from types import SimpleNamespace
from unittest.mock import Mock, call

from ash.ash import Ash
from ash.commands import JT_COMMANDS, ROOT_COMMANDS


LS_JOBS_COMMAND = "ls jobs project:demo nightly result_limit:5"


class BareAsh(Ash):
    def __init__(self):
        pass


class TestAshBehavior(unittest.TestCase):
    def setUp(self):
        self.ash = BareAsh()
        self.ash.print = Mock()
        self.ash.commands = ROOT_COMMANDS.copy()
        self.ash.completer = None

    def test_run_dispatches_known_command_with_args(self):
        self.ash.session = Mock()
        self.ash.session.prompt = Mock(side_effect=[LS_JOBS_COMMAND, "exit"])
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
            loaded, by_id, by_name = self.ash._get_objects("inventories")

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
            loaded, by_id, by_name = self.ash._get_objects("projects")

        self.assertEqual(loaded, objects)
        self.assertEqual(by_id, {10: objects[0], 11: objects[1]})
        self.assertEqual(by_name, {"Project A": objects[0], "Project B": objects[1]})
        self.ash.aap.get_projects.assert_called_once_with()
        self.ash.cache.insert_cache.assert_has_calls(
            [call("projects", 10, objects[0]), call("projects", 11, objects[1])]
        )

    def test_filter_objects_supports_named_filters_and_plain_search(self):
        matching = SimpleNamespace(
            name="Deploy App",
            data={
                "summary_fields": {"project": {"name": "Core Platform"}},
                "project": "core-platform",
            },
        )
        other = SimpleNamespace(
            name="Cleanup",
            data={
                "summary_fields": {"project": {"name": "Operations"}},
                "project": "operations",
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
        self.ash.session_wo_history.prompt = Mock(side_effect=["", "yes"])
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


if __name__ == "__main__":
    unittest.main()
