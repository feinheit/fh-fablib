from __future__ import unicode_literals

from fabric.api import (
    env, execute, hide, hosts, run, runs_once, settings, task)
from fabric.colors import red
from fabric.utils import abort, puts

from fh_fablib import (
    cd, confirm, run_local, require_env, require_services, step
)


def complain_on_failure(task, complaint):
    if not task.succeeded:
        puts(red(complaint))


@task(default=True)
@hosts('')
@runs_once
def check():
    """Runs coding style checks, and Django's checking framework"""
    step('Checking Python code with flake8...')
    run_local('PYTHONWARNINGS=ignore venv/bin/flake8 .')

    step('Checking Javascript code...')
    run_local('./node_modules/.bin/eslint %(box_static_src)s webpack*js')

    step('Invoking Django\'s systems check framework...')
    run_local('venv/bin/python manage.py check')

    with settings(warn_only=True), hide('warnings'):
        # Remind the user about uglyness, but do not fail (there are good
        # reasons to use the patterns warned about here).
        step('Pointing to potential tasks...')
        run_local(
            "! git --no-pager grep -n -C3 -E '^[^#]+import i?pdb' -- '*.py'")
        run_local(
            "! git --no-pager grep -n -C3 -E '^[^#]+print( |\(|$)' -- '*.py'")
        run_local(
            "! git --no-pager grep -n -C3 -E 'console\.log' -- '*.html' '*.js'"
        )
        run_local(
            "! git --no-pager grep -n -E '#.*noqa'"
            " -- '%(box_project_name)s/*.py'")
        run_local("! git --no-pager grep -n -E '(XXX|FIXME|TODO)'")
        complain_on_failure(
            run_local("! git --no-pager grep -n -E '^-e.+$' -- requirements*"),
            'Warning: Editable requirements found. Releases are preferred!')


@task
@runs_once
@require_env
def deploy():
    """Checks whether everything is ready for deployment"""

    step('Checking whether we are on the expected branch...')
    with settings(warn_only=True), hide('everything'):
        branch = run_local('git symbolic-ref -q --short HEAD', capture=True)

    if not branch:
        abort(red('No branch checked out, cannot continue.', bold=True))

    if branch != env.box_branch:
        puts(red(
            'Warning: The currently checked out branch is \'%s\', but'
            ' the environment \'%s\' runs on \'%s\'.' % (
                branch, env.box_environment, env.box_branch)))

        if not confirm('Continue deployment?', default=False):
            abort('Aborting.')

    execute('check.check')
    execute('check.test')

    with cd('%(box_domain)s'):
        step('\nChecking for uncommitted changes on the server...')
        result = run('git status --porcelain')
        if result:
            abort(red('Uncommitted changes detected, aborting deployment.'))


@task
@runs_once
@hosts('')
@require_services
def test():
    step('Running backend testsuite...')
    run_local('venv/bin/python manage.py test app')
    step('We do not have a frontend testsuite yet...')
    # run_local('./node_modules/.bin/gulp test')
