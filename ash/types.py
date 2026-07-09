#!/usr/bin/env python

"""Shared type definitions for ash."""

from enum import Enum


class ContextType(str, Enum):
    """Represents the type of object currently in focus."""
    JOB_TEMPLATES = 'job_templates'
    JOBS = 'jobs'
    INVENTORIES = 'inventories'
    PROJECTS = 'projects'
