from __future__ import unicode_literals

from datetime import datetime
from io import StringIO
import os

from fabric.api import env, execute, hide, prompt, put, settings, task
from fabric.colors import green, red
from fabric.utils import abort, puts

from fh_fablib import confirm, run_local, cd, require_env, run
from fh_fablib.utils import get_random_string, remote_env


@task
@require_env
def setup():
    """Sets up the server from a git repository"""
    execute("server.clone_repository")
    execute("server.create_virtualenv")
    execute("server.create_database_and_dotenv")
    execute("server.nginx_vhost_and_supervisor")
    execute("deploy")


@task
@require_env
def clone_repository():
    puts(green("We need the repository to initialize the server."))
    with hide("running"):
        output = run_local("git config remote.origin.url", capture=True)
    repo = prompt("Repository", default=output)

    if not repo:
        puts(red("Cannot continue without a repository."))
        return 1

    env.box_repository_url = repo

    run("git clone -b %(box_branch)s %(box_repository_url)s %(box_domain)s")
    execute("git.add_remote")


@task
@require_env
def create_virtualenv():
    with cd("%(box_domain)s"):
        run("rm -rf venv")
        run("python3 -m venv venv")
        run("venv/bin/pip install -U pip wheel setuptools")
        run("venv/bin/pip install -r requirements.txt")


@task
@require_env
def create_database_and_dotenv():
    env.box_sentry_dsn = prompt("Sentry DSN")
    env.box_oauth2_client_id = prompt("Google OAuth2 Client ID")
    env.box_oauth2_client_secret = prompt("Google OAuth2 Client Secret")

    env.box_database_pw = get_random_string(
        20, chars="abcdefghijklmopqrstuvwx01234567890"
    )
    env.box_secret_key = get_random_string(50)

    run(
        'psql -c "CREATE ROLE %(box_database)s WITH'
        " ENCRYPTED PASSWORD '%(box_database_pw)s'"
        ' LOGIN NOCREATEDB NOCREATEROLE NOSUPERUSER"'
    )
    run('psql -c "GRANT %(box_database)s TO admin"')
    run(
        'psql -c "CREATE DATABASE %(box_database)s WITH'
        " OWNER %(box_database)s"
        " TEMPLATE template0"
        " ENCODING 'UTF8'\""
    )

    with cd("%(box_domain)s"):

        put(
            StringIO(
                """\
DEBUG=False
DATABASE_URL=postgres://%(box_database)s:%(box_database_pw)s\
@localhost:5432/%(box_database)s
CACHE_URL=hiredis://localhost:6379/1/?key_prefix=%(box_database)s
SECRET_KEY=%(box_secret_key)s
SENTRY_DSN=%(box_sentry_dsn)s
ALLOWED_HOSTS=['.%(box_domain)s', '.%(host_string_host)s']

GOOGLE_CLIENT_ID=%(box_oauth2_client_id)s
GOOGLE_CLIENT_SECRET=%(box_oauth2_client_secret)s

# LIVE=True
# CANONICAL_DOMAIN=%(box_domain)s
# CANONICAL_DOMAIN_SECURE=True
"""
                % dict(env, host_string_host=env.host_string.split("@")[-1])
            ),
            ".env",
        )

        run("venv/bin/python manage.py migrate --noinput")


@task
@require_env
def nginx_vhost_and_supervisor():
    run(
        "sudo nine-manage-vhosts virtual-host create %(box_domain)s"
        " --template=%(box_vhost_template)s"
        " --webroot=/home/www-data/%(box_domain)s/htdocs"
    )

    with cd("%(box_domain)s"):
        run("mkdir -p media tmp")

    for line in env["box_enable_process"]:
        run(line)


@task
@require_env
def ssl():
    run("sudo nine-manage-vhosts certificate create" " --virtual-host=%(box_domain)s")
    run(
        "sudo nine-manage-vhosts virtual-host update %(box_domain)s"
        " --template=%(box_vhost_ssl_template)s"
    )


@task
@require_env
def add_alias(alias):
    env.box_nmv_alias = alias
    run(
        "sudo nine-manage-vhosts alias create %(box_nmv_alias)s"
        " --virtual-host=%(box_domain)s"
    )
    run(
        "sudo nine-manage-vhosts alias create www.%(box_nmv_alias)s"
        " --virtual-host=%(box_domain)s"
    )


@task
@require_env
def remove_alias(alias):
    env.box_nmv_alias = alias
    run(
        "sudo nine-manage-vhosts alias remove %(box_nmv_alias)s"
        " --virtual-host=%(box_domain)s"
    )
    run(
        "sudo nine-manage-vhosts alias remove www.%(box_nmv_alias)s"
        " --virtual-host=%(box_domain)s"
    )


@task
@require_env
def copy_data_from(environment=None):
    """
    Copy the database from one environment to another. Usually from production
    to stage.

    Usage: ``fab s server.copy_data_from:production``.
    :param environment: the source environment
    """
    if env.get("box_hardwired_environment"):
        abort(red("Cannot continue with a hardwired environment."))
    if environment not in env.box_environments:
        abort(red("Invalid environment %s." % environment))
    source = env.box_environments[environment]
    target = env.box_environments[env.get("box_environment")]
    if source == target:
        abort(
            red(
                "Source environment %s must not equal target environment %s."
                % (environment, env.get("box_environment"))
            )
        )

    if source["servers"][0] != target["servers"][0]:
        abort(red("The environments have to be on the same server, sorry!"))

    puts("Copying data from {0} to {1}".format(source["remote"], target["remote"]))
    if not confirm(
        "Completely replace the remote database" ' "%(box_database)s" (if it exists)?',
        default=False,
    ):
        return

    for key, value in source.items():
        env["source_%s" % key] = value

    with settings(warn_only=True):
        run("dropdb %(box_database)s")
    run(
        "createdb %(box_database)s --encoding=UTF8 --template=template0"
        " --owner=%(box_database)s"
    )
    run("pg_dump -Ox %(source_database)s | psql %(box_database)s")
    run('psql %(box_database)s -c "REASSIGN OWNED BY admin ' ' TO %(box_database)s"')

    with cd(env.box_domain):
        run("cp -aln ~/%(source_domain)s/media/* media/")

    execute("server.restart")


@task
@require_env
def remove_host():
    if not confirm(
        'Really remove the host "%(box_domain)s" and all associated data?',
        default=False,
    ):
        return

    run("sudo nine-manage-vhosts virtual-host remove %(box_domain)s")
    for line in env["box_disable_process"]:
        run(line)
    with cd(env.box_domain):
        env.box_datetime = datetime.now().strftime("%Y-%m-%d-%s")
        run(
            "pg_dump -Ox %(box_database)s"
            " > %(box_database)s-%(box_environment)s-%(box_datetime)s.sql"
        )
    run("dropdb %(box_database)s")
    run("dropuser %(box_database)s")

    puts(
        red(
            "The folder ~/%(box_domain)s on the server has not been removed. The"
            " project folder also contains a fresh database dump." % env
        )
    )


@task
@require_env
def dump_db():
    """Dumps the database into the tmp/ folder"""
    env.box_datetime = datetime.now().strftime("%Y-%m-%d-%s")
    env.box_dump_filename = os.path.join(
        os.getcwd(),
        "tmp",
        "%(box_database)s-%(box_environment)s-%(box_datetime)s.sql" % env,
    )

    env.box_remote_db = remote_env("DATABASE_URL")
    if not env.box_remote_db:
        abort(red("Unable to determine the remote DATABASE_URL", bold=True))

    run_local(
        "ssh %(host_string)s pg_dump -Ox %(box_remote_db)s" " > %(box_dump_filename)s"
    )
    puts(green("\nWrote a dump to %(box_dump_filename)s" % env))


@task
@require_env
def load_db(filename=None):
    """Loads a dump into the database"""
    env.box_dump_filename = filename

    if not filename:
        abort(red('Dump missing. "fab server.load_db:filename"', bold=True))

    if not os.path.exists(filename):
        abort(red('"%(box_dump_filename)s" does not exist.' % env, bold=True))

    if not confirm(
        "Completely replace the remote database" ' "%(box_database)s" (if it exists)?',
        default=False,
    ):
        return

    env.box_remote_db = remote_env("DATABASE_URL")
    if not env.box_remote_db:
        abort(red("Unable to determine the remote DATABASE_URL", bold=True))

    run('psql -c "DROP DATABASE IF EXISTS %(box_database)s"')
    run(
        "createdb %(box_database)s --encoding=UTF8 --template=template0"
        " --owner=%(box_database)s"
    )
    run_local(
        "cat %(box_dump_filename)s |" " ssh %(host_string)s psql %(box_remote_db)s"
    )
    run('psql %(box_database)s -c "REASSIGN OWNED BY admin ' ' TO %(box_database)s"')


@task
@require_env
def dbshell():
    # env.box_remote_db = remote_env('DATABASE_URL')
    # ssh SERVER -o RequestTTY=yes\
    # 'psql $(grep -E "^DATABASE_URL=" %(box_domain)s/.env | cut -f2 -d=)'
    run("psql %(box_database)s")


@task
@require_env
def restart():
    """Restart the server process"""
    for line in env["box_restart"]:
        run(line)
