from __future__ import unicode_literals

from datetime import datetime
import os

from fabric.api import env, execute, hosts, settings, task
from fabric.colors import green, red
from fabric.contrib.project import rsync_project
from fabric.utils import abort, puts

from fh_fablib import confirm, run, run_local, require_env, require_services
from fh_fablib.utils import get_random_string


@task
@hosts('')
@require_services
def setup():
    """Initial setup of the project. Use ``setup_with_production_data`` instead
    if the project is already installed on a server"""
    if os.path.exists('venv'):
        puts(red('It seems that this project is already set up, aborting.'))
        return 1

    if not os.path.exists('venv'):
        execute('local.create_virtualenv')
    execute('local.frontend_tools')
    if not os.path.exists('.env'):
        execute('local.create_dotenv')
    execute('local.create_and_migrate_database')

    puts(green(
        'Initial setup has completed successfully!', bold=True))
    puts(green(
        'Next steps:'))
    puts(green(
        '- Update the README: edit README.rst'))
    puts(green(
        '- Create a superuser: venv/bin/python manage.py createsuperuser'))
    puts(green(
        '- Run the development server: fab dev'))
    puts(green(
        '- Create a Bitbucket repository: fab git.init_bitbucket'))
    puts(green(
        '- Configure a server for this project: fab server.setup'
        % env))


@task
@require_env
@require_services
def setup_with_production_data():
    """Installs all dependencies and pulls the database and mediafiles from
    the server to create an instant replica of the production environment"""
    if os.path.exists('venv'):
        puts(red('It seems that this project is already set up, aborting.'))
        return 1

    execute('local.create_virtualenv')
    execute('local.frontend_tools')
    execute('local.create_dotenv')
    execute('local.pull_database')
    execute('local.empty_to_password')

    puts(green(
        'Setup with production data has completed successfully!', bold=True))
    puts(green(
        'Next steps:'))
    puts(green(
        '- Create a superuser: venv/bin/python manage.py createsuperuser'))
    puts(green(
        '- Run the development server: fab dev'))


@task
@hosts('')
@require_services
def update():
    execute('local.backend_tools')
    execute('local.frontend_tools')


@task
@hosts('')
def create_virtualenv():
    """Creates the virtualenv and installs all Python requirements"""
    run_local('python3 -m venv venv')
    run_local('venv/bin/pip install -U wheel pip')
    if os.path.exists('requirements.txt'):
        run_local('venv/bin/pip install -r requirements.txt')
    else:
        run_local('venv/bin/pip install -U -r requirements-to-freeze.txt')
        run_local(
            '(printf "# AUTOGENERATED, DO NOT EDIT\n\n";'
            'venv/bin/pip freeze -l'
            # Until Ubuntu gets its act together:
            ' | grep -vE "(^pkg-resources)"'
            ') > requirements.txt')


@task
@hosts('')
def update_requirements():
    """Update requirements.txt"""
    run_local('rm -rf venv requirements.txt')
    execute('local.create_virtualenv')


@task
@hosts('')
def frontend_tools():
    """Installs frontend tools. Knows how to handle npm/bower and bundler"""
    run_local('yarn')


@task
@hosts('')
def backend_tools():
    run_local('venv/bin/pip install -r requirements.txt')
    run_local('find . -name "*.pyc" -delete')
    run_local('venv/bin/python manage.py migrate')


@task
@hosts('')
def create_dotenv():
    """Creates a .env file containing basic configuration for
    local development"""
    with open('.env', 'w') as f:
        env.box_secret_key = get_random_string(50)
        f.write('''\
DATABASE_URL=postgres://localhost:5432/%(box_database_local)s
CACHE_URL=hiredis://localhost:6379/1/?key_prefix=%(box_database_local)s
SECRET_KEY=%(box_secret_key)s
SENTRY_DSN=
ALLOWED_HOSTS=['*']
''' % env)


@task
@hosts('')
@require_services
def create_and_migrate_database():
    """Creates and migrates a Postgres database"""

    if not confirm(
            'Completely replace the local database'
            ' "%(box_database_local)s" (if it exists)?'):
        return

    run_local(
        'dropdb --if-exists %(box_database_local)s')
    run_local(
        'createdb %(box_database_local)s'
        ' --encoding=UTF8 --template=template0')
    with settings(warn_only=True):
        run_local('venv/bin/python manage.py makemigrations elephantblog')
        run_local('venv/bin/python manage.py makemigrations page')
    run_local('venv/bin/python manage.py migrate')


@task
@require_env
@require_services
def pull_database():
    """Pulls the database contents from the server, dropping the local
    database first (if it exists)"""

    if not confirm(
            'Completely replace the local database'
            ' "%(box_database_local)s" (if it exists)?'):
        return

    env.box_remote_db = run(
        "grep -E '^DATABASE_URL=' %(box_domain)s/.env | cut -f2 -d="
    ).splitlines()[0].strip()

    if not env.box_remote_db:
        abort(red('Unable to determine the remote DATABASE_URL', bold=True))

    run_local(
        'dropdb --if-exists %(box_database_local)s')
    run_local(
        'createdb %(box_database_local)s'
        ' --encoding=UTF8 --template=template0')
    run_local(
        'ssh %(host_string)s pg_dump -Ox "%(box_remote_db)s"'
        ' | psql %(box_database_local)s')


@task
@require_env
@require_services
def empty_to_password():
    run_local(
        'venv/bin/python manage.py update_empty_passwords password')
    puts(green(
        'Users with empty passwords (for example SSO users) now have a'
        ' password of "password" (without quotes).'))


@task
@require_env
def pull_mediafiles():
    """Pulls all mediafiles from the server. Beware, it is possible that this
    command pulls down several GBs!"""
    if not confirm('Completely replace local mediafiles?'):
        return
    rsync_project(
        local_dir='media/',
        remote_dir='%(box_domain)s/media/' % env,
        delete=False,  # Devs can take care of their media folders.
        upload=False,
    )


@task
@require_env
@require_services
def pull():
    # local.backend_tools without migrate step
    run_local('venv/bin/pip install -r requirements.txt')
    run_local('find . -name "*.pyc" -delete')

    execute('local.pull_database')
    execute('local.empty_to_password')
    execute('local.update')


@task
@require_env
@require_services
def dump_db():
    """Dumps the database into the tmp/ folder"""
    env.box_datetime = datetime.now().strftime('%Y-%m-%d-%s')
    env.box_dump_filename = os.path.join(
        os.getcwd(),
        'tmp',
        '%(box_database)s-local-%(box_datetime)s.sql' % env,
    )

    run_local(
        'pg_dump %(box_database_local)s --no-privileges --no-owner'
        ' --no-reconnect > %(box_dump_filename)s')
    puts(green('\nWrote a dump to %(box_dump_filename)s' % env))


@task
@require_env
@require_services
def load_db(filename=None):
    """Loads a dump into the database"""
    env.box_dump_filename = filename

    if not filename:
        abort(red('Dump missing. "fab local.load_db:filename"', bold=True))

    if not os.path.exists(filename):
        abort(red('"%(box_dump_filename)s" does not exist.' % env, bold=True))

    run_local('dropdb --if-exists %(box_database_local)s')
    run_local(
        'createdb %(box_database_local)s'
        ' --encoding=UTF8 --template=template0')
    run_local('psql %(box_database_local)s < %(box_dump_filename)s')
