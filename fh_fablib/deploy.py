from __future__ import unicode_literals

from fabric.api import env, execute, task
from fabric.contrib.project import rsync_project

from fh_fablib import run_local, cd, require_env, run, step


@task(default=True)
@require_env
def deploy(*args):
    """Deploys frontend and backend code to the server if the checking step
    did not report any problems"""
    step("\nChecking whether we are up to date...")
    run_local("git push --dry-run origin %(box_branch)s")

    execute("check.deploy")

    step("\nCompiling static sources...")
    run_local("yarn run prod")

    step("\nPushing changes...")
    run_local("git push origin %(box_branch)s")

    step("\nDeploying new code on server...")
    with cd("%(box_domain)s"):
        run("git fetch")
        run("git merge --ff-only origin/%(box_branch)s")

    _do_deploy(args)


@task
@require_env
def direct():
    """Deploys code directly, most useful when Bitbucket is down"""
    execute("check.deploy")

    step("\nCompiling static sources...")
    run_local("yarn run prod")

    step("\nPushing changes...")
    run_local("git push %(box_remote)s %(box_branch)s:refs/heads/DIRECTDEPLOY")

    step("\nDeploying new code on server...")
    with cd("%(box_domain)s"):
        run("git merge --ff-only DIRECTDEPLOY")

    _do_deploy()

    run_local("git push %(box_remote)s :refs/heads/DIRECTDEPLOY")
    step("\nPLEASE do not forget to push to the source repository anyway!")


def _do_deploy(args=()):
    with cd("%(box_domain)s"):
        run('find . -name "*.pyc" -delete')
        run("venv/bin/pip install -U pip wheel setuptools")
        run("venv/bin/pip install -r requirements.txt")
        run("venv/bin/python manage.py migrate --noinput")

    step("\nUploading static files...")
    rsync_project(
        local_dir="static/",
        remote_dir="%(box_domain)s/static/" % env,
        delete=("clear" in args),
    )

    step("\nCollecting static files...")
    with cd("%(box_domain)s"):
        run("venv/bin/python manage.py collectstatic --noinput")

    step("\nRunning system checks on server...")
    with cd("%(box_domain)s"):
        run("venv/bin/python manage.py check --deploy")

    step("\nRestarting server process...")
    execute("server.restart")

    execute("git.fetch_remote")
