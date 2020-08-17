import io
import os
import random
import re
import shutil
import tempfile
import warnings
from pathlib import Path  # noqa, re-export

import speckenv
from fabric import Connection, task
from invoke import Collection  # noqa, re-export


# I don't care, in this context.
warnings.simplefilter("ignore", category=ResourceWarning)


class Env(dict):
    __getattr__ = dict.__getitem__

    def update(self, data):
        super().update(data)
        if self.get("base"):
            os.chdir(self["base"])
            pre_commit_hook()


#: Defaults
env = Env({"app": "app", "branch": "main"})


class Connection(Connection):
    """Connection subclass which makes c.run() echo all commands"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.config["run"]["echo"] = True


def pre_commit_hook():
    """Install the pre-commit hook running coding style checks"""
    path = env.base / ".git" / "hooks" / "pre-commit"
    if not path.exists():
        with path.open("w") as hook:
            hook.write("#!/bin/sh\nfab check\n")
        path.chmod(0o755)


def get_random_string(length, chars=None):
    """Returns a random string; mostly used to generate passwords and
    the contents of SECRET_KEY"""
    rand = random.SystemRandom()
    if chars is None:
        chars = "abcdefghijklmnopqrstuvwxyz0123456789!@#$%^&*(-_=+)"
    return "".join(rand.choice(chars) for i in range(length))


def _check_flake8(ctx):
    ctx.run("venv/bin/flake8 .")


def _check_django(ctx):
    ctx.run("venv/bin/python manage.py check")


def _check_prettier(ctx):
    ctx.run(
        f'yarn run prettier --list-different *.js "{env.app}/static/**/*.js"'
        f' "{env.app}/static/**/*.scss"'
    )


def _check_eslint(ctx):
    ctx.run(f"yarn run eslint *.js {env.app}/static")


@task
def dev(ctx, host="127.0.0.1", port=8000):
    """Run the development server for the frontend and backend"""
    with tempfile.NamedTemporaryFile("w+") as f:
        # https://gist.github.com/jiaaro/b2e1b7c705022c2cf56888152a999f65
        f.write(
            """\
trap "exit" INT TERM
trap "kill 0" EXIT

export PYTHONWARNINGS=always
export PYTHONUNBUFFERED=yes

venv/bin/python manage.py runserver 0.0.0.0:%(port)s &
HOST=%(host)s yarn run dev &

for job in $(jobs -p); do wait $job; done
"""
            % {"host": host, "port": port}
        )
        f.flush()

        ctx.run("bash %s" % f.name)


def _fmt_prettier(ctx):
    ctx.run(
        f'yarn run prettier --write *.js "{env.app}/static/**/*.js"'
        f' "{env.app}/static/**/*.scss"'
    )


def _fmt_tox_style(ctx):
    ctx.run('env PATH="$PATH" tox -e style')


def _srv_deploy(conn, *, rsync_static):
    with conn.cd(env.domain):
        conn.run(f"git checkout {env.branch}")
        conn.run("git fetch origin")
        conn.run(f"git merge --ff-only origin/{env.branch}")
        conn.run('find . -name "*.pyc" -delete')
        conn.run("venv/bin/pip install -U pip wheel setuptools")
        conn.run("venv/bin/pip install -r requirements.txt")
        conn.run("venv/bin/python manage.py migrate")
    if rsync_static:
        conn.local(f"rsync -avz --delete static/ {env.host}:{env.domain}static")
    with conn.cd(env.domain):
        conn.run("venv/bin/python manage.py collectstatic --noinput")
        conn.run("venv/bin/python manage.py check --deploy", warn=True)


@task
def pull_db(ctx):
    """Pull a local copy of the remote DB and reset all passwords"""
    with Connection(env.host) as conn:
        e = _srv_env(conn, f"{env.domain}/.env")

    srv_dsn = e("DATABASE_URL")
    local_dsn = _local_env()("DATABASE_URL")
    dbname = local_dsn.rsplit("/", 1)[-1]

    ctx.run(f"dropdb --if-exists {dbname}", warn=True)
    ctx.run(f"createdb {dbname}")
    ctx.run(f"ssh {env.host} -C 'pg_dump -Ox {srv_dsn}' | psql {local_dsn}")
    ctx.run(
        'venv/bin/python manage.py shell -c "'
        "from django.contrib.auth import get_user_model;"
        "c=get_user_model();u=c();u.set_password('password');"
        'c.objects.update(password=u.password)"',
        echo=True,
    )


def _local_env(path=".env"):
    mapping = {}
    speckenv.read_speckenv(env.base / path, mapping=mapping)

    return lambda *a, **kw: speckenv.env(*a, **kw, mapping=mapping)


def _srv_env(conn, path):
    mapping = {}

    with tempfile.NamedTemporaryFile() as f:
        conn.get(path, f.name)
        speckenv.read_speckenv(f.name, mapping=mapping)

    return lambda *a, **kw: speckenv.env(*a, **kw, mapping=mapping)


@task
def mm(ctx):
    """Update the translation catalogs"""
    ctx.run(
        "PATH=/usr/bin:/usr/sbin "
        "venv/bin/python manage.py makemessages -a -i venv -i htmlcov"
        " --add-location file",
    )
    ctx.run(
        "PATH=/usr/bin:/usr/sbin "
        "venv/bin/python manage.py makemessages -a -i venv -i htmlcov"
        " --add-location file"
        " -i node_modules -i lib"
        " -d djangojs",
    )


@task
def cm(ctx):
    """Compile the translation catalogs"""
    ctx.run(
        "PATH=/usr/bin:/usr/sbin "
        "venv/bin/python manage.py compilemessages -i venv -i htmlcov"
    )


def _python3():
    interpreters = ("python3.9", "python3.8", "python3.7", "python3.6")
    return next(filter(None, (shutil.which(v) for v in interpreters)))


@task
def upgrade(ctx):
    """Re-create the virtualenv with newest versions of all libraries"""
    ctx.run("rm -rf venv")
    ctx.run(f"{_python3()} -m venv venv")
    ctx.run("venv/bin/pip install -U pip wheel setuptools")
    ctx.run("venv/bin/pip install -U -r requirements-to-freeze.txt --pre")
    freeze(ctx)


@task
def freeze(ctx):
    """Freeze the virtualenv's state"""
    ctx.run(
        '(printf "# AUTOGENERATED, DO NOT EDIT\n\n";'
        "venv/bin/pip freeze -l"
        # Until Ubuntu gets its act together:
        ' | grep -vE "(^pkg-resources)"'
        ") > requirements.txt",
    )


@task
def update(ctx):
    """Update virtualenv and node_modules to match the lockfiles"""
    if not os.path.exists("venv"):
        ctx.run(f"{_python3()} -m venv venv")
    ctx.run("venv/bin/pip install -U pip wheel setuptools")
    ctx.run("venv/bin/pip install -r requirements.txt")
    ctx.run('find . -name "*.pyc" -delete')
    ctx.run("yarn")
    ctx.run("venv/bin/python manage.py migrate")


def _local_dotenv_if_not_exists():
    if os.path.exists(".env"):
        return

    secret_key = get_random_string(50)
    dbname = re.sub(r"[^a-z0-9]+", "_", env.domain)

    with open(".env", "w") as f:
        f.write(
            f"""\
DATABASE_URL=postgres://localhost:5432/{dbname}
CACHE_URL=hiredis://localhost:6379/1/?key_prefix={dbname}
SECRET_KEY={secret_key}
SENTRY_DSN=
ALLOWED_HOSTS=["*"]
DEBUG=True
"""
        )


def _local_dbname():
    _local_dotenv_if_not_exists()
    return _local_env()("DATABASE_URL").rsplit("/", 1)[-1]


@task
def local(ctx):
    """Local environment setup"""
    dbname = _local_dbname()
    ctx.run(f"createdb {dbname}", warn=True)
    update(ctx)


@task
def nine_vhost(ctx):
    """Create a virtual host using nine-manage-vhosts"""
    with Connection(env.host) as conn:
        conn.run(
            f"sudo nine-manage-vhosts virtual-host create {env.domain}"
            " --template=feinheit_cache"
            " --webroot=/home/www-data/{env.domain}/htdocs"
        )
        with conn.cd(env.domain):
            conn.run("mkdir -f media tmp")


@task
def nine_alias_add(ctx, alias):
    """Add aliasses to a nine-manage-vhost virtual host"""
    with Connection(env.host) as conn:
        conn.run(
            f"sudo nine-manage-vhosts alias create --virtual-host={env.domain}"
            f" {alias}"
        )
        conn.run(
            f"sudo nine-manage-vhosts alias create --virtual-host={env.domain}"
            f" www.{alias}",
            warn=True,
        )


@task
def nine_alias_remove(ctx, alias):
    """Remove aliasses from a nine-manage-vhost virtual host"""
    with Connection(env.host) as conn:
        conn.run(
            f"sudo nine-manage-vhosts alias remove --virtual-host={env.domain}"
            f" {alias}"
        )
        conn.run(
            f"sudo nine-manage-vhosts alias create --virtual-host={env.domain}"
            f" www.{alias}",
            warn=True,
        )


@task
def nine_unit(ctx):
    """Start and enable a gunicorn@ unit"""
    with Connection(env.host) as conn:
        conn.run(f"systemctl --user start gunicorn@{env.domain}.service")
        conn.run(f"systemctl --user enable gunicorn@{env.domain}.service")


@task
def nine_db_dotenv(ctx):
    """Create a database and initialize the .env"""
    with Connection(env.host) as conn:
        password = get_random_string(20)
        secret_key = get_random_string(50)

        conn.run(
            f'psql -c "CREATE ROLE {env.database} WITH'
            f" ENCRYPTED PASSWORD '{password}'"
            f' LOGIN NOCREATEDB NOCREATEROLE NOSUPERUSER"'
        )
        conn.run(f'psql -c "GRANT {env.database} TO admin"')
        conn.run(
            f'psql -c "CREATE DATABASE {env.database} WITH'
            f" OWNER {env.database} TEMPLATE template0 ENCODING 'UTF8'"
            f'"'
        )
        conn.put(
            io.StringIO(
                f"""\
DEBUG=False
DATABASE_URL=postgres://{env.database}:{password}@localhost:5432/{env.database}
CACHE_URL=hiredis://localhost:6379/1/?key_prefix={env.database}
SECRET_KEY={secret_key}
SENTRY_DSN=
ALLOWED_HOSTS=[".{env.domain}", ".{conn.host}"]
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=

# LIVE=True
# CANONICAL_DOMAIN={env.domain}
# CANONICAL_DOMAIN_SECURE=True
"""
                % dict(env, host_string_host=env.host_string.split("@")[-1])
            ),
            ".env",
        )


@task
def nine_ssl(ctx):
    """Activate SSL"""
    with Connection(env.host) as conn:
        conn.run(
            f"sudo nine-manage-vhosts certificate create --virtual-host={env.domain}"
        )
        conn.run(
            f"sudo nine-manage-vhosts virtual-host update {env.domain}"
            f" --template=feinheit_cache_letsencrypt"
        )


@task
def nine_disable(ctx):
    """Disable a virtual host, dump and remove the DB and stop the gunicorn@ unit"""
    with Connection(env.host) as conn:
        conn.run(f"sudo nine-manage-vhosts virtual-host remove {env.domain}")
        conn.run(f"systemctl --user stop gunicorn@{env.domain}.service")
        conn.run(f"systemctl --user disable gunicorn@{env.domain}.service")
        e = _srv_env(conn, f"{env.domain}/.env")
        srv_dsn = e("DATABASE_URL")
        conn.run(f"pg_dump -Ox {srv_dsn} > DUMP.sql")
        conn.run(f"dropdb {env.database}")
        conn.run(f"dropuser {env.database}")


@task
def nine_checkout(ctx):
    """Checkout the repository on the server"""
    repo = ctx.run("git config remote.origin.url", hide=True).stdout
    with Connection(env.host, forward_agent=True) as conn:
        conn.run(f"git clone {repo} {env.domain} -b {env.branch}")


@task
def nine_venv(ctx):
    """Create a venv and install packages from requirements.txt"""
    with Connection(env.host, forward_agent=True) as conn:
        with conn.cd(env.domain):
            conn.run("python3 -m venv venv")
            conn.run("venv/bin/pip install -U pip wheel setuptools")
            conn.run("venv/bin/pip install -r requirements.txt")


@task
def nine(ctx):
    """Run all nine🌟 setup tasks in order"""
    nine_checkout(ctx)
    nine_venv(ctx)
    nine_db_dotenv(ctx)
    nine_vhost(ctx)
    nine_unit(ctx)
    # nine_ssl(ctx)      Does not apply
    # nine_disable(ctx)  Does obviously not apply 😅


@task
def bitbucket(ctx):
    """Create a repository on Bitbucket and push the code"""
    e = _local_env(Path.home() / ".box.env")
    print("Username: ", end="")
    username = input(e("BITBUCKET_USERNAME"))
    print("Password: ", end="")
    password = input(e("BITBUCKET_PASSWORD"))
    print("Organization: ", end="")
    organization = input(e("BITBUCKET_ORGANIZATION"))
    print("Repository: ", end="")
    repository = input(env.domain)

    ctx.run(
        f"""\
curl -X POST -v -u {username}:"{password}" -H "content-type: application/json"\
 https://api.bitbucket.org/2.0/repositories/{organization}/{repository}\
 -d '{{"scm": "git", "is_private": true, "forking_policy": "no_public_forks"}}'\
"""
    )
    ctx.run(f"git remote add origin git@bitbucket.org:{organization}/{repository}.git")
    ctx.run(f"git push -u origin {env.branch}")


@task
def fetch(ctx):
    """Add and fetch refs from the server"""
    ctx.run(
        f"git remote add {env.remote} {env.host}:{env.domain}", warn=True, hide=True
    )
    ctx.run(f"git fetch {env.remote}")


@task
def check(ctx):
    """Check the coding style"""
    _check_flake8(ctx)
    _check_django(ctx)
    _check_prettier(ctx)
    _check_eslint(ctx)


@task
def fmt(ctx):
    """Format the code"""
    _fmt_prettier(ctx)
    _fmt_tox_style(ctx)


GENERAL = {
    cm,
    dev,
    mm,
    upgrade,
    freeze,
    update,
    pull_db,
    local,
    bitbucket,
    fetch,
    check,
    fmt,
}
NINE = {
    nine_vhost,
    nine_alias_add,
    nine_alias_remove,
    nine_unit,
    nine_db_dotenv,
    nine_ssl,
    nine_disable,
    nine_checkout,
    nine_venv,
    nine,
}
