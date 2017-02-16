from __future__ import unicode_literals

import os

from fabric.api import env, execute, put, task
from fabric.contrib.project import rsync_project

from fh_fablib import run_local, cd, require_env, run, step


@task(default=True)
@require_env
def deploy(*args):
    """Deploys frontend and backend code to the server if the checking step
    did not report any problems"""
    execute('check.deploy')

    webpack2 = os.path.exists('postcss.config.js')

    step('\nCompiling static sources...')

    if webpack2:
        run_local('npm run prod')
    else:
        run_local('rm -rf %(box_static_src)s/dist' % env)
        run_local(
            './node_modules/.bin/webpack --config webpack.prod.config.js')

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
    if webpack2:
        rsync_project(
            local_dir='static/',
            remote_dir='%(box_domain)s/static/' % env,
            delete=('clear' in args),
        )
    else:
        rsync_project(
            local_dir='%(box_static_src)s/dist' % env,
            remote_dir='%(box_domain)s/%(box_staticfiles)s/' % env,
            delete=True,
        )
        put(
            'tmp/webpack*json',
            '%(box_domain)s/tmp/' % env,
        )

    step('\nCollecting static files...')
    with cd('%(box_domain)s'):
        run('venv/bin/python manage.py collectstatic --noinput')

    step('\nRestarting server process...')
    for line in env['box_restart']:
        run(line)

    execute('git.fetch_remote')
