import io
import os
import random
import re
import shutil
import sys
import tempfile
import warnings
from pathlib import Path  # noqa, re-export

import speckenv
from fabric import Connection, task
from invoke import Collection  # noqa, re-export


__version__ = "1.0.20200819"


# I don't care, in this context.
warnings.simplefilter("ignore", category=ResourceWarning)
os.environ["FABRIC_RUN_ECHO"] = "1"
os.environ["FABRIC_RUN_PTY"] = "True"


def ansi(code):
    return lambda s: "\033[{}m{}\033[0m".format(code, s)


# underline = ansi("4")
red = ansi("31")
green = ansi("32")


def terminate(msg):
    print(red(msg), file=sys.stderr)
    sys.exit(1)


def require(version):
    if __version__ < version:
        terminate(f"fh_fablib version {version} required (you have {__version__})")


class Config:
    app = "app"

    def update(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)

        os.chdir(self.base)
        pre_commit_hook()

    def __getattr__(self, key):
        terminate(f"Configuration key '{key}' not set")


#: Defaults
config = Config()


class Connection(Connection):
    """Connection subclass which makes c.run() echo all commands"""

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("forward_agent", True)
        super().__init__(*args, **kwargs)
        self.config["run"]["echo"] = True
        self.config["run"]["pty"] = True


def pre_commit_hook():
    """Install the pre-commit hook running coding style checks"""
    path = config.base / ".git" / "hooks" / "pre-commit"
    if not path.exists():
        with path.open("w") as hook:
            hook.write("#!/bin/sh\nfab check\n")
        path.chmod(0o755)


def _random_string(length, chars=None):
    """Returns a random string; mostly used to generate passwords and
    the contents of SECRET_KEY"""
    rand = random.SystemRandom()
    if chars is None:
        chars = "abcdefghijklmnopqrstuvwxyz0123456789!@#$%^&*(-_=+)"
    return "".join(rand.choice(chars) for i in range(length))


def _dbname_from_dsn(dsn):
    return dsn.rsplit("/", 1)[-1]


def _dbname_from_domain(domain):
    return re.sub(r"[^a-z0-9]+", "_", domain)


def _concurrently(ctx, jobs):
    with tempfile.NamedTemporaryFile("w+", prefix="fab.", suffix=".sh") as f:
        jobs = "\n".join(f"{job} &" for job in jobs)
        # https://gist.github.com/jiaaro/b2e1b7c705022c2cf56888152a999f65
        f.write(
            f"""\
trap "exit" INT TERM
trap "kill 0" EXIT

export PYTHONWARNINGS=always
export PYTHONUNBUFFERED=yes

{jobs}

for job in $(jobs -p); do wait $job; done
"""
        )
        f.flush()
        ctx.run(f"bash {f.name}", replace_env=False)


@task
def dev(ctx, host="127.0.0.1", port=8000):
    """Run the development server for the frontend and backend"""
    print(green(f"Starting server at http://{host}:{port}/"))
    _concurrently(
        ctx,
        [
            f"venv/bin/python manage.py runserver 0.0.0.0:{port}",
            f'HOST="{host}" yarn run dev',
        ],
    )


def _reset_passwords(ctx):
    ctx.run(
        'venv/bin/python manage.py shell -c "'
        "from django.contrib.auth import get_user_model;"
        "U=get_user_model();u=U();u.set_password('password');"
        'U.objects.update(password=u.password)"'
    )


@task
def pull_db(ctx):
    """Pull a local copy of the remote DB and reset all passwords"""
    with Connection(config.host) as conn:
        e = _srv_env(conn, f"{config.domain}/.env")

    srv_dsn = e("DATABASE_URL")
    local_dsn = _local_env()("DATABASE_URL")
    dbname = _dbname_from_dsn(local_dsn)

    ctx.run(f"dropdb --if-exists {dbname}", warn=True)
    ctx.run(f"createdb {dbname}")
    ctx.run(f"ssh {config.host} -C 'pg_dump -Ox {srv_dsn}' | psql {local_dsn}")

    _reset_passwords(ctx)


def _local_env(path=".env"):
    mapping = {}
    speckenv.read_speckenv(config.base / path, mapping=mapping)

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
        "venv/bin/python manage.py makemessages -a --add-location file"
        " -i venv -i htmlcov",
        replace_env=False,
    )
    ctx.run(
        "venv/bin/python manage.py makemessages -a --add-location file"
        " -i venv -i htmlcov -i node_modules -i lib"
        " -d djangojs",
        replace_env=False,
    )


@task
def cm(ctx):
    """Compile the translation catalogs"""
    ctx.run(
        "venv/bin/python manage.py compilemessages"
        " -i venv -i htmlcov -i node_modules -i lib",
        replace_env=False,
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
    venv = config.base / "venv"
    if not venv.exists():
        ctx.run(f"{_python3()} -m venv venv")
    ctx.run("venv/bin/pip install -U pip wheel setuptools")
    ctx.run("venv/bin/pip install -r requirements.txt")
    ctx.run('find . -name "*.pyc" -delete')
    ctx.run("yarn")
    ctx.run("venv/bin/python manage.py migrate")


def _local_dotenv_if_not_exists():
    dotenv = config.base / ".env"
    if dotenv.exists():
        return

    secret_key = _random_string(50)
    dbname = _dbname_from_domain(config.domain)

    with dotenv.open("w") as f:
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
    return _dbname_from_dsn(_local_env()("DATABASE_URL"))


@task
def local(ctx):
    """Local environment setup"""
    dbname = _local_dbname()
    ctx.run(f"createdb {dbname}", warn=True)
    update(ctx)


@task
def nine_vhost(ctx):
    """Create a virtual host using nine-manage-vhosts"""
    with Connection(config.host) as conn:
        conn.run(
            f"sudo nine-manage-vhosts virtual-host create {config.domain}"
            " --template=feinheit_cache"
            " --webroot=/home/www-data/{config.domain}/htdocs"
        )
        with conn.cd(config.domain):
            conn.run("mkdir -f media tmp")


@task
def nine_alias_add(ctx, alias):
    """Add aliasses to a nine-manage-vhost virtual host"""
    with Connection(config.host) as conn:
        conn.run(
            f"sudo nine-manage-vhosts alias create --virtual-host={config.domain}"
            f" {alias}"
        )
        conn.run(
            f"sudo nine-manage-vhosts alias create --virtual-host={config.domain}"
            f" www.{alias}",
            warn=True,
        )


@task
def nine_alias_remove(ctx, alias):
    """Remove aliasses from a nine-manage-vhost virtual host"""
    with Connection(config.host) as conn:
        conn.run(
            f"sudo nine-manage-vhosts alias remove --virtual-host={config.domain}"
            f" {alias}"
        )
        conn.run(
            f"sudo nine-manage-vhosts alias create --virtual-host={config.domain}"
            f" www.{alias}",
            warn=True,
        )


@task
def nine_unit(ctx):
    """Start and enable a gunicorn@ unit"""
    with Connection(config.host) as conn:
        conn.run(f"systemctl --user start gunicorn@{config.domain}.service")
        conn.run(f"systemctl --user enable gunicorn@{config.domain}.service")


@task
def nine_db_dotenv(ctx):
    """Create a database and initialize the .env"""
    with Connection(config.host) as conn:
        password = _random_string(20)
        secret_key = _random_string(50)
        dbname = _dbname_from_domain(config.domain)

        conn.run(
            f'psql -c "CREATE ROLE {dbname} WITH'
            f" ENCRYPTED PASSWORD '{password}'"
            f' LOGIN NOCREATEDB NOCREATEROLE NOSUPERUSER"'
        )
        conn.run(f'psql -c "GRANT {dbname} TO admin"')
        conn.run(
            f'psql -c "CREATE DATABASE {dbname} WITH'
            f" OWNER {dbname} TEMPLATE template0 ENCODING 'UTF8'"
            f'"'
        )
        conn.put(
            io.StringIO(
                f"""\
DEBUG=False
DATABASE_URL=postgres://{dbname}:{password}@localhost:5432/{dbname}
CACHE_URL=hiredis://localhost:6379/1/?key_prefix={dbname}
SECRET_KEY={secret_key}
SENTRY_DSN=
ALLOWED_HOSTS=[".{config.domain}", ".{conn.host}"]
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=

# LIVE=True
# CANONICAL_DOMAIN={config.domain}
# CANONICAL_DOMAIN_SECURE=True
"""
            ),
            ".env",
        )


@task
def nine_ssl(ctx):
    """Activate SSL"""
    with Connection(config.host) as conn:
        conn.run(
            f"sudo nine-manage-vhosts certificate create --virtual-host={config.domain}"
        )
        conn.run(
            f"sudo nine-manage-vhosts virtual-host update {config.domain}"
            f" --template=feinheit_cache_letsencrypt"
        )


@task
def nine_disable(ctx):
    """Disable a virtual host, dump and remove the DB and stop the gunicorn@ unit"""
    with Connection(config.host) as conn:
        conn.run(f"sudo nine-manage-vhosts virtual-host remove {config.domain}")
        conn.run(f"systemctl --user stop gunicorn@{config.domain}.service")
        conn.run(f"systemctl --user disable gunicorn@{config.domain}.service")
        e = _srv_env(conn, f"{config.domain}/.env")
        srv_dsn = e("DATABASE_URL")
        conn.run(f"pg_dump -Ox {srv_dsn} > DUMP.sql")
        srv_dbname = _dbname_from_dsn(srv_dsn)
        conn.run(f"dropdb {srv_dbname}")
        conn.run(f"dropuser {srv_dbname}")


@task
def nine_checkout(ctx):
    """Checkout the repository on the server"""
    repo = ctx.run("git config remote.origin.url", hide=True).stdout
    with Connection(config.host) as conn:
        conn.run(f"git clone {repo} {config.domain} -b {config.branch}")


@task
def nine_venv(ctx):
    """Create a venv and install packages from requirements.txt"""
    with Connection(config.host) as conn:
        with conn.cd(config.domain):
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
    repository = input(config.domain)

    ctx.run(
        f"""\
curl -X POST -v -u {username}:"{password}" -H "content-type: application/json"\
 https://api.bitbucket.org/2.0/repositories/{organization}/{repository}\
 -d '{{"scm": "git", "is_private": true, "forking_policy": "no_public_forks"}}'\
"""
    )
    ctx.run(f"git remote add origin git@bitbucket.org:{organization}/{repository}.git")
    ctx.run(f"git push -u origin {config.branch}")


@task
def fetch(ctx):
    """Ensure a remote exists for the server and fetch"""
    ctx.run(
        f"git remote add {config.remote} {config.host}:{config.domain}",
        warn=True,
        hide=True,
    )
    ctx.run(f"git fetch {config.remote}")


def _check_flake8(ctx):
    ctx.run("venv/bin/flake8 .")


def _check_django(ctx):
    ctx.run("venv/bin/python manage.py check")


def _check_prettier(ctx):
    ctx.run(
        f'yarn run prettier --list-different "*.js" "{config.app}/static/**/*.js"'
        f' "{config.app}/static/**/*.scss"'
    )


def _check_eslint(ctx):
    ctx.run(f'yarn run eslint "*.js" {config.app}/static')


@task
def check(ctx):
    """Check the coding style"""
    _check_flake8(ctx)
    _check_django(ctx)
    _check_prettier(ctx)
    _check_eslint(ctx)


def _fmt_prettier(ctx):
    ctx.run(
        f'yarn run prettier --write "*.js" "{config.app}/static/**/*.js"'
        f' "{config.app}/static/**/*.scss"'
    )


def _fmt_tox_style(ctx):
    ctx.run("tox -e style", pty=True, replace_env=False)


@task
def fmt(ctx):
    """Format the code"""
    _fmt_prettier(ctx)
    _fmt_tox_style(ctx)


@task
def deploy(ctx):
    """Deploy once 🔥"""
    branch = ctx.run("git rev-parse --abbrev-ref HEAD", hide=True).stdout.strip()
    if branch != config.branch:
        terminate(f"Current branch is '{branch}', should be '{config.branch}'")

    check(ctx)
    ctx.run(f"git push origin {config.branch}")
    ctx.run("yarn run prod")

    with Connection(config.host) as conn:
        with conn.cd(config.domain):
            conn.run(f"git checkout {config.branch}")
            conn.run("git fetch origin")
            conn.run(f"git merge --ff-only origin/{config.branch}")
            conn.run('find . -name "*.pyc" -delete')
            conn.run("venv/bin/pip install -U pip wheel setuptools")
            conn.run("venv/bin/pip install -r requirements.txt")
            conn.run("venv/bin/python manage.py migrate")
            conn.run("venv/bin/python manage.py check --deploy", warn=True)
        conn.local(
            f"rsync -pthrz --delete static/ {config.host}:{config.domain}/static/"
        )
        with conn.cd(config.domain):
            conn.run("venv/bin/python manage.py collectstatic --noinput")
        conn.run(f"systemctl --user restart gunicorn@{config.domain}.service")

    fetch(ctx)


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
    deploy,
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
