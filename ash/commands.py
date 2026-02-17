#!/usr/bin/env python

from collections import OrderedDict

ROOT_COMMANDS = OrderedDict([
    ('cd', 'Change context to a specific object (e.g., job_template <name_or_id>)'),
    ('ls', 'List all objects of a certain type (e.g., job_templates, inventories)'),
    ('cache', 'Refresh cached data from AAP (mostly for auto-completion)'),
    ('exit', 'Quit program')
])

CD_COMMANDS = OrderedDict([
    ('job_template', 'Change context to a specific job template by name or ID'),
    ('inventory', 'Change context to a specific inventory by name or ID'),
    ('project', 'Change context to a specific project by name or ID'),
    ('job', 'Change context to a specific job by name or ID')
])

LS_COMMANDS = OrderedDict([
    ('job_templates', 'List all job templates or fuzzy filtered by any field'),
    ('inventories', 'List all inventories or fuzzy filtered by any field'),
    ('projects', 'List all projects or fuzzy filtered by any field'),
    ('jobs', 'List all jobs or fuzzy filtered by any field')
])

JT_COMMANDS = OrderedDict([
    ('launch', 'job_template: Launch the selected job template'),
    ('refresh', 'job_template: Refresh the selected job template information'),
    ('info', 'job_template: Show information about the selected job template'),
    ('set', 'job_template: Set parameters for the selected job template'),
    ('jobs', 'job_template: List jobs launched from the selected job template'),
    ('sync', 'job_template: Sync the project associated with the selected job template')
])

JOB_COMMANDS = OrderedDict([
    ('info', 'job: Show information about the selected job'),
    ('refresh', 'job: Refresh the selected job information'),
    ('retry', 'job: Retry the selected job'),
    ('reuse', 'job: Reuse the selected job parameters as prefill for a new job'),
    ('template', 'job: Switch context to the job template of the selected job'),
    ('cancel', 'job: Cancel the selected job'),
    ('output', 'job: Show output of the selected job')
])

INVENTORY_COMMANDS = OrderedDict([
    ('info', 'inventory: Show information about the selected inventory'),
    ('refresh', 'inventory: Refresh the selected inventory'),
    ('hosts', 'inventory: List hosts in the selected inventory'),
    ('groups', 'inventory: List groups in the selected inventory')
])

PROJECT_COMMANDS = OrderedDict([
    ('info', 'project: Show information about the selected project'),
    ('refresh', 'project: Refresh the selected project information'),
    ('sync', 'project: Sync the selected project')
])

LS_JOB_TEMPLATE_FILTERS = OrderedDict([
    ('created_by', 'Filter by the user who created the job template.'),
    ('modified_by', 'Filter by the user who last modified the job template.'),
    ('labels', 'Filter by labels associated with the job template.'),
    ('inventory', 'Filter by the inventory used in the job template.'),
    ('project', 'Filter by the project associated with the job template.'),
    ('organization', 'Filter by the organization that owns the job template.'),
    ('playbook', 'Filter by the playbook used in the job template.')
])

LS_JOBS_FILTERS = OrderedDict([
    ('created_by', 'Filter by the user who created the job.'),
    ('labels', 'Filter by labels associated with the job.'),
    ('inventory', 'Filter by the inventory used in the job.'),
    ('project', 'Filter by the project associated with the job.'),
    ('organization', 'Filter by the organization that owns the job.'),
    ('result_limit', 'Limit the number of results returned (e.g., result_limit:100)')
])

LS_PROJECTS_FILTERS = OrderedDict([
    ('created_by', 'Filter by the user who created the project.'),
    ('modified_by', 'Filter by the user who last modified the project.'),
    ('organization', 'Filter by the organization that owns the project.')
])

LS_INVENTORIES_FILTERS = OrderedDict([
    ('created_by', 'Filter by the user who created the inventory.'),
    ('modified_by', 'Filter by the user who last modified the inventory.'),
    ('hosts', 'Filter by hosts in the inventory.'),
    ('job_templates', 'Filter by job templates associated with the inventory.'),
    ('organization', 'Filter by the organization that owns the inventory.')
])
