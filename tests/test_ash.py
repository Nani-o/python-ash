import io
import unittest
from contextlib import redirect_stdout
from types import SimpleNamespace
from unittest.mock import Mock, call

from ash.ash import Ash
from ash.commands import ROOT_COMMANDS


class AshBehaviorTests(unittest.TestCase):
    def make_ash(self):
        ash = Ash.__new__(Ash)
        ash.print = Mock()
        ash.commands = ROOT_COMMANDS.copy()
        ash.completer = None
        return ash

    def test_run_dispatches_known_command_with_args(self):
        ash = self.make_ash()
        ash.session = Mock()
        ash.session.prompt = Mock(side_effect=["ls jobs result_limit:5", "exit"])
        ash.get_prompt = Mock(return_value=[])

        calls = []
        ash._Ash__cmd_ls = lambda args: calls.append(args)

        with redirect_stdout(io.StringIO()):
            ash.run()

        self.assertEqual(calls, [["jobs", "result_limit:5"]])

    def test_get_objects_uses_cache_when_available(self):
        ash = self.make_ash()
        objects = [
            SimpleNamespace(id=1, name="Inventory A"),
            SimpleNamespace(id=2, name="Inventory B"),
        ]
        ash.cache = Mock()
        ash.cache.load_cache.return_value = objects
        ash.aap = Mock()

        with redirect_stdout(io.StringIO()):
            loaded, by_id, by_name = ash._get_objects("inventories")

        self.assertEqual(loaded, objects)
        self.assertEqual(by_id, {1: objects[0], 2: objects[1]})
        self.assertEqual(by_name, {"Inventory A": objects[0], "Inventory B": objects[1]})
        ash.aap.get_inventories.assert_not_called()
        ash.cache.insert_cache.assert_not_called()

    def test_get_objects_fetches_and_caches_when_cache_is_empty(self):
        ash = self.make_ash()
        objects = [
            SimpleNamespace(id=10, name="Project A"),
            SimpleNamespace(id=11, name="Project B"),
        ]
        ash.cache = Mock()
        ash.cache.load_cache.return_value = []
        ash.aap = Mock()
        ash.aap.get_projects.return_value = objects

        with redirect_stdout(io.StringIO()):
            loaded, by_id, by_name = ash._get_objects("projects")

        self.assertEqual(loaded, objects)
        self.assertEqual(by_id, {10: objects[0], 11: objects[1]})
        self.assertEqual(by_name, {"Project A": objects[0], "Project B": objects[1]})
        ash.aap.get_projects.assert_called_once_with()
        ash.cache.insert_cache.assert_has_calls(
            [call("projects", 10, objects[0]), call("projects", 11, objects[1])]
        )

    def test_parse_ls_jobs_args_builds_filters_and_limit(self):
        ash = self.make_ash()

        filters, result_limit = ash._Ash__parse_ls_jobs_args(
            ["project:demo", "nightly", "result_limit:25"]
        )

        self.assertEqual(filters, {"project__search": ["demo"], "search": ["nightly"]})
        self.assertEqual(result_limit, 25)

    def test_parse_ls_jobs_args_rejects_invalid_result_limit(self):
        ash = self.make_ash()

        filters, result_limit = ash._Ash__parse_ls_jobs_args(["result_limit:not-a-number"])

        self.assertIsNone(filters)
        self.assertIsNone(result_limit)
        ash.print.assert_called_once()

    def test_filter_objects_supports_named_filters_and_plain_search(self):
        ash = self.make_ash()
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

        result = ash.filter_objects([matching, other], ["project:core", "deploy"], {"project": ""})

        self.assertEqual(result, [matching])

    def test_cmd_launch_merges_prompted_values_and_survey_vars(self):
        ash = self.make_ash()
        ash.current_context = Mock()
        ash.current_context.get_asked_variables.return_value = ["inventory", "extra_vars"]
        ash.current_context.survey_enabled = True
        ash.current_context.get_survey_spec.return_value = [{"variable": "branch"}]

        prompted_values = {
            "inventory": ("inventory", 42),
            "extra_vars": ("extra_vars", {"env": "prod"}),
        }
        ash._ask_variable = Mock(side_effect=lambda var: prompted_values[var])
        ash._Ash__handle_survey = Mock(return_value={"branch": "main"})

        captured = []
        ash._Ash__execute_payload = lambda template, payload: captured.append((template, payload))

        ash._Ash__cmd_launch([])

        self.assertEqual(
            captured,
            [(ash.current_context, {"inventory": 42, "extra_vars": {"env": "prod", "branch": "main"}})],
        )


if __name__ == "__main__":
    unittest.main()
