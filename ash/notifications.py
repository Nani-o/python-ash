#!/usr/bin/env python

"""Optional desktop notifications for completed jobs."""

import shutil
import subprocess


def notify_job_finished(job):
    """Notify that a job finished when terminal-notifier is available."""
    notifier = shutil.which("terminal-notifier")
    if not notifier:
        return False

    try:
        subprocess.run(
            [
                notifier,
                "-title",
                "ASH - Job finished",
                "-message",
                f"Job {job.id} ({job.name}) finished with status: {job.status}",
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except (OSError, subprocess.CalledProcessError):
        return False

    return True
