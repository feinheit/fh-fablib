from __future__ import unicode_literals

from fabric.api import env, execute, task
from fabric.contrib.project import rsync_project

from fh_fablib import run_local, cd, require_env, run, step


@task(default=True)
@require_env
def deploy(*args):
    """Deploys frontend and backend code to the server if the checking step
    did not report any problems"""
    execute('check.deploy')

    step('\nCompiling static sources...')
    run_local('yarn run prod')

    step('\nPushing changes...')
    run_local('git push origin %(box_branch)s')

    step('\nDeploying new code on server...')
    with cd('%(box_domain)s'):
        run('git fetch')
        run('git reset --hard origin/%(box_branch)s')
        run('find . -name "*.pyc" -delete')
        run('venv/bin/pip install -r requirements.txt')
        run('venv/bin/python manage.py migrate --noinput')

    step('\nUploading static files...')
    rsync_project(
        local_dir='static/',
        remote_dir='%(box_domain)s/static/' % env,
        delete=('clear' in args),
    )

    step('\nCollecting static files...')
    with cd('%(box_domain)s'):
        run('venv/bin/python manage.py collectstatic --noinput')

    step('\nRunning system checks on server...')
    with cd('%(box_domain)s'):
        run('venv/bin/python manage.py check --deploy')

    step('\nRestarting server process...')
    for line in env['box_restart']:
        run(line)

    execute('git.fetch_remote')
