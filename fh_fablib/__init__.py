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


def _check_flake8(c):
    c.run("venv/bin/flake8 .")


def _check_django(c):
    c.run("venv/bin/python manage.py check")


def _check_prettier(c):
    c.run(
        f'yarn run prettier --list-different *.js "{env.app}/static/**/*.js"'
        f' "{env.app}/static/**/*.scss"'
    )


def _check_eslint(c):
    c.run(f"yarn run eslint *.js {env.app}/static")


@task
def dev(c, host="127.0.0.1", port=8000):
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

        c.run("bash %s" % f.name)


def _fmt_prettier(c):
    c.run(
        f'yarn run prettier --write *.js "{env.app}/static/**/*.js"'
        f' "{env.app}/static/**/*.scss"'
    )


def _fmt_tox_style(c):
    c.run('env PATH="$PATH" tox -e style')


def _srv_deploy(c, *, rsync_static):
    with c.cd(env.domain):
        c.run(f"git checkout {env.branch}")
        c.run("git fetch origin")
        c.run(f"git merge --ff-only origin/{env.branch}")
        c.run('find . -name "*.pyc" -delete')
        c.run("venv/bin/pip install -U pip wheel setuptools")
        c.run("venv/bin/pip install -r requirements.txt")
        c.run("venv/bin/python manage.py migrate")
    if rsync_static:
        c.local(f"rsync -avz --delete static/ {env.host}:{env.domain}static")
    with c.cd(env.domain):
        c.run("venv/bin/python manage.py collectstatic --noinput")
        c.run("venv/bin/python manage.py check --deploy", warn=True)


@task
def pull_db(c):
    """Pull a local copy of the remote DB and reset all passwords"""
    with Connection(env.host) as remote:
        e = _srv_env(remote, f"{env.domain}/.env")

    srv_dsn = e("DATABASE_URL")
    local_dsn = _local_env()("DATABASE_URL")
    dbname = local_dsn.rsplit("/", 1)[-1]

    c.run(f"dropdb --if-exists {dbname}", warn=True)
    c.run(f"createdb {dbname}")
    c.run(f"ssh {env.host} -C 'pg_dump -Ox {srv_dsn}' | psql {local_dsn}")
    c.run(
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


def _srv_env(c, path):
    mapping = {}

    with tempfile.NamedTemporaryFile() as f:
        c.get(path, f.name)
        speckenv.read_speckenv(f.name, mapping=mapping)

    return lambda *a, **kw: speckenv.env(*a, **kw, mapping=mapping)


@task
def mm(c):
    """Update the translation catalogs"""
    c.run(
        "PATH=/usr/bin:/usr/sbin "
        "venv/bin/python manage.py makemessages -a -i venv -i htmlcov"
        " --add-location file",
    )
    c.run(
        "PATH=/usr/bin:/usr/sbin "
        "venv/bin/python manage.py makemessages -a -i venv -i htmlcov"
        " --add-location file"
        " -i node_modules -i lib"
        " -d djangojs",
    )


@task
def cm(c):
    """Compile the translation catalogs"""
    c.run(
        "PATH=/usr/bin:/usr/sbin "
        "venv/bin/python manage.py compilemessages -i venv -i htmlcov"
    )


def _python3():
    interpreters = ("python3.9", "python3.8", "python3.7", "python3.6")
    return next(filter(None, (shutil.which(v) for v in interpreters)))


@task
def upgrade(c):
    """Re-create the virtualenv with newest versions of all libraries"""
    c.run("rm -rf venv")
    c.run(f"{_python3()} -m venv venv")
    c.run("venv/bin/pip install -U pip wheel setuptools")
    c.run("venv/bin/pip install -U -r requirements-to-freeze.txt --pre")
    freeze(c)


@task
def freeze(c):
    """Freeze the virtualenv's state"""
    c.run(
        '(printf "# AUTOGENERATED, DO NOT EDIT\n\n";'
        "venv/bin/pip freeze -l"
        # Until Ubuntu gets its act together:
        ' | grep -vE "(^pkg-resources)"'
        ") > requirements.txt",
    )


@task
def update(c):
    """Update virtualenv and node_modules to match the lockfiles"""
    if not os.path.exists("venv"):
        c.run(f"{_python3()} -m venv venv")
    c.run("venv/bin/pip install -U pip wheel setuptools")
    c.run("venv/bin/pip install -r requirements.txt")
    c.run('find . -name "*.pyc" -delete')
    c.run("yarn")
    c.run("venv/bin/python manage.py migrate")


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
def local(c):
    """Local environment setup"""
    dbname = _local_dbname()
    c.run(f"createdb {dbname}", warn=True)
    update(c)


@task
def nine_vhost(c):
    """Create a virtual host using nine-manage-vhosts"""
    with Connection(env.host) as c:
        c.run(
            f"sudo nine-manage-vhosts virtual-host create {env.domain}"
            " --template=feinheit_cache"
            " --webroot=/home/www-data/{env.domain}/htdocs"
        )
        with c.cd(env.domain):
            c.run("mkdir -f media tmp")


@task
def nine_unit(c):
    """Start and enable a gunicorn@ unit"""
    with Connection(env.host) as c:
        c.run(f"systemctl --user start gunicorn@{env.domain}.service")
        c.run(f"systemctl --user enable gunicorn@{env.domain}.service")


@task
def nine_db_dotenv(c):
    """Create a database and initialize the .env"""
    with Connection(env.host) as c:
        password = get_random_string(20)
        secret_key = get_random_string(50)

        c.run(
            f'psql -c "CREATE ROLE {env.database} WITH'
            f" ENCRYPTED PASSWORD '{password}'"
            f' LOGIN NOCREATEDB NOCREATEROLE NOSUPERUSER"'
        )
        c.run(f'psql -c "GRANT {env.database} TO admin"')
        c.run(
            f'psql -c "CREATE DATABASE {env.database} WITH'
            f" OWNER {env.database} TEMPLATE template0 ENCODING 'UTF8'"
            f'"'
        )
        c.put(
            io.StringIO(
                f"""\
DEBUG=False
DATABASE_URL=postgres://{env.database}:{password}@localhost:5432/{env.database}
CACHE_URL=hiredis://localhost:6379/1/?key_prefix={env.database}
SECRET_KEY={secret_key}
SENTRY_DSN=
ALLOWED_HOSTS=[".{env.domain}", ".{c.host}"]
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
def nine_ssl(c):
    """Activate SSL"""
    with Connection(env.host) as c:
        c.run(f"sudo nine-manage-vhosts certificate create --virtual-host={env.domain}")
        c.run(
            f"sudo nine-manage-vhosts virtual-host update {env.domain}"
            f" --template=feinheit_cache_letsencrypt"
        )


@task
def nine_disable(c):
    """Disable a virtual host, dump and remove the DB and stop the gunicorn@ unit"""
    with Connection(env.host) as c:
        c.run(f"sudo nine-manage-vhosts virtual-host remove {env.domain}")
        c.run(f"systemctl --user stop gunicorn@{env.domain}.service")
        c.run(f"systemctl --user disable gunicorn@{env.domain}.service")
        e = _srv_env(c, f"{env.domain}/.env")
        srv_dsn = e("DATABASE_URL")
        c.run(f"pg_dump -Ox {srv_dsn} > DUMP.sql")
        c.run(f"dropdb {env.database}")
        c.run(f"dropuser {env.database}")


@task
def nine_checkout(c):
    """Checkout the repository on the server"""
    repo = c.run("git config remote.origin.url", hide=True).stdout
    with Connection(env.host, forward_agent=True) as c:
        c.run(f"git clone {repo} {env.domain} -b {env.branch}")


@task
def nine_venv(c):
    """Create a venv and install packages from requirements.txt"""
    with Connection(env.host, forward_agent=True) as c:
        with c.cd(env.domain):
            c.run("python3 -m venv venv")
            c.run("venv/bin/pip install -U pip wheel setuptools")
            c.run("venv/bin/pip install -r requirements.txt")


@task
def nine(c):
    """Run all nine🌟 setup tasks in order"""
    nine_checkout(c)
    nine_venv(c)
    nine_db_dotenv(c)
    nine_vhost(c)
    nine_unit(c)
    # nine_ssl(c)      Does not apply
    # nine_disable(c)  Does obviously not apply 😅


@task
def bitbucket(c):
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

    c.run(
        f"""\
curl -X POST -v -u {username}:"{password}" -H "content-type: application/json"\
 https://api.bitbucket.org/2.0/repositories/{organization}/{repository}\
 -d '{{"scm": "git", "is_private": true, "forking_policy": "no_public_forks"}}'\
"""
    )
    c.run(f"git remote add origin git@bitbucket.org:{organization}/{repository}.git")
    c.run(f"git push -u origin {env.branch}")
