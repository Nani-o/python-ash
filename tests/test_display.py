import copy
import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from ash.display import Display
from ash.models import Job


class TestJobDisplay(unittest.TestCase):
    def setUp(self):
        self.display = Display(None)
        self.display.print = Mock()
        self.api = Mock(base_url='https://aap.example/')
        self.revision = 'a1b2c3d' + '0' * 33

    def make_job(self, **overrides):
        data = {
            'id': 42,
            'created': '',
            'limit': '',
            'name': 'Deploy',
            'playbook': 'deploy.yml',
            'status': 'successful',
            'project': 7,
            'scm_branch': '',
            'scm_revision': self.revision,
        }
        data.update(overrides)
        return Job(self.api, data)

    def assert_scm_label(self, job, projects, expected):
        self.display.print.reset_mock()
        original_data = copy.deepcopy(job.data)
        original_attributes = vars(job).copy()

        self.display.display_jobs([job], projects_by_id=projects)

        header, header_color = self.display.print.call_args_list[0].args
        row, row_color = self.display.print.call_args_list[1].args
        branch_start = header.index('scm_branch')
        status_start = header.index('status')
        self.assertEqual(row[branch_start:status_start].strip(), expected)
        self.assertEqual(row[status_start:].strip(), job.status)
        self.assertEqual(header_color, 'headers')
        self.assertEqual(row_color, 'blue_bold')
        self.assertEqual(job.data, original_data)
        self.assertEqual(vars(job), original_attributes)
        self.api.assert_not_called()
        self.assertEqual(self.api.mock_calls, [])

    def test_scm_reference_priority_and_fallbacks(self):
        project = SimpleNamespace(scm_branch='release/v1.2', scm_revision=self.revision)
        cases = [
            ('job branch', {'scm_branch': 'feature/deploy'}, {7: project}, 'feature/deploy'),
            ('job tag without revision', {'scm_branch': 'v1.1', 'scm_revision': ''}, {7: project}, 'v1.1'),
            ('matching revision', {}, {7: project}, 'release/v1.2'),
            ('different revision', {'scm_revision': 'f' * 40}, {7: project}, 'fffffff'),
            ('same short prefix', {'scm_revision': 'a1b2c3d' + 'f' * 33}, {7: project}, 'a1b2c3d'),
            ('missing project', {}, {}, 'a1b2c3d'),
            ('null project', {'project': None}, {7: project}, 'a1b2c3d'),
            ('empty cache list', {}, [], 'a1b2c3d'),
            ('empty project branch', {}, {7: SimpleNamespace(scm_branch='', scm_revision=self.revision)}, 'a1b2c3d'),
            ('empty project revision', {}, {7: SimpleNamespace(scm_branch='main', scm_revision='')}, 'a1b2c3d'),
            ('empty job revision', {'scm_revision': ''}, {7: project}, 'unknown'),
            ('both revisions empty', {'scm_revision': ''}, {7: SimpleNamespace(scm_branch='main', scm_revision='')}, 'unknown'),
            ('null revision', {'scm_revision': None}, {7: project}, 'unknown'),
        ]
        for name, overrides, projects, expected in cases:
            with self.subTest(name=name):
                self.assert_scm_label(self.make_job(**overrides), projects, expected)

    def test_missing_optional_fields_and_project_mapping(self):
        job = self.make_job()
        for field in ('scm_branch', 'scm_revision', 'project'):
            delattr(job, field)
            del job.data[field]

        self.assert_scm_label(job, None, 'unknown')
        self.display.display_jobs([self.make_job()])
        self.assertIn('a1b2c3d', self.display.print.call_args.args[0])

    def test_resolved_reference_controls_width_and_truncation(self):
        for branch in ('release/production', 'release/' + 'x' * 30):
            with self.subTest(branch=branch):
                project = SimpleNamespace(scm_branch=branch, scm_revision=self.revision)
                expected = branch if len(branch) <= 25 else branch[:22] + '...'
                self.assert_scm_label(self.make_job(), {7: project}, expected)
                header = self.display.print.call_args_list[0].args[0]
                self.assertEqual(header.index('status') - header.index('scm_branch'), min(len(branch), 25) + 3)


if __name__ == '__main__':
    unittest.main()
