from __future__ import unicode_literals

from fabric.api import env, execute, hide, hosts, run, runs_once, settings, task
from fabric.colors import red
from fabric.utils import abort, puts

from fh_fablib import cd, confirm, run_local, require_env, require_services, step


@task(default=True)
@hosts("")
@runs_once
def check():
    """Runs coding style checks, and Django's checking framework"""
    step("\nRunning coding style checks...")
    for cmd in env["box_check"]:
        run_local(cmd)


@task
@runs_once
@require_env
def deploy():
    """Checks whether everything is ready for deployment"""

    step("Checking whether we are on the expected branch...")
    with settings(warn_only=True), hide("everything"):
        branch = run_local("git symbolic-ref -q --short HEAD", capture=True)

    if not branch:
        abort(red("No branch checked out, cannot continue.", bold=True))

    if branch != env.box_branch:
        puts(
            red(
                "Warning: The currently checked out branch is '%s', but"
                " the environment '%s' runs on '%s'."
                % (branch, env.box_environment, env.box_branch)
            )
        )

        if not confirm("Continue deployment?", default=False):
            abort("Aborting.")

    execute("check.check")
    execute("check.test")

    with cd("%(box_domain)s"):
        step("\nChecking for uncommitted changes on the server...")
        result = run("git status --porcelain")
        if result:
            abort(red("Uncommitted changes detected, aborting deployment."))


@task
@runs_once
@hosts("")
@require_services
def test():
    step("\nRunning the test suite...")
    for cmd in env["box_test"]:
        run_local(cmd)
