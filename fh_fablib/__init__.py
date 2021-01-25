import io
import os
import random
import re
import shutil
import sys
import tempfile
import warnings
from pathlib import Path

import speckenv
from fabric import Connection, task
from invoke import Collection  # noqa, re-export


__version__ = "1.0.20210125"


# I don't care, in this context.
warnings.simplefilter("ignore", category=ResourceWarning)


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


def run(c, *a, **kw):
    """A Context.run or Connection.run with better defaults"""
    kw.setdefault("echo", True)
    kw.setdefault("pty", True)
    kw.setdefault("replace_env", False)
    return c.run(*a, **kw)


class Config:
    app = "app"
    environments = {}

    def update(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)

        os.chdir(self.base)
        pre_commit_hook()

    def __getattr__(self, key):
        environments = self.__dict__.get("environments", "")
        if environments:
            environments = f" [{', '.join(sorted(environments))}]"
        terminate(
            f"Configuration key '{key}' not set. "
            f"Maybe you forgot to set an environment with which to interact?"
            f"{environments}"
        )


#: Defaults
config = Config()


def environment(name, cfg, **kwargs):
    config.environments[name] = cfg

    @task(name=name, **kwargs)
    def fn(ctx):
        config.update(**cfg)

    fn.__doc__ = f'Set the environment to "{name}"'
    return fn


class Connection(Connection):
    """Connection subclass which always forwards the agent by default"""

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("forward_agent", True)
        super().__init__(*args, **kwargs)


def pre_commit_hook(*, force=False):
    """Install the pre-commit hook running coding style checks"""
    path = config.base / ".git" / "hooks" / "pre-commit"
    if not path.exists() or force:
        with path.open("w") as hook:
            hook.write("#!/bin/sh\nfl check\n")
        path.chmod(0o755)


def _random_string(length, *, chars=None):
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
    with tempfile.NamedTemporaryFile("w+", prefix="fl.", suffix=".sh") as f:
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
        run(ctx, f"bash {f.name}", replace_env=False)


@task
def hook(ctx):
    """Install the pre-commit hook"""
    pre_commit_hook(force=True)


@task(auto_shortflags=False)
def dev(ctx, host="127.0.0.1", port=8000):
    """Run the development server for the frontend and backend"""
    print(green(f"Starting server at http://{host}:{port}/"))
    _concurrently(
        ctx,
        [
            f"venv/bin/python manage.py runserver 0.0.0.0:{port}",
            f'HOST="{host}" npx webpack-dev-server --host 0.0.0.0 --port 4000 --hot',
        ],
    )


@task
def pull_db(ctx):
    """Pull a local copy of the remote DB and reset all passwords"""
    with Connection(config.host) as conn:
        e = _srv_env(conn, f"{config.domain}/.env")

    srv_dsn = e("DATABASE_URL")
    local_dsn = _local_env()("DATABASE_URL")
    dbname = _dbname_from_dsn(local_dsn)

    run(ctx, f"dropdb --if-exists {dbname}", warn=True)
    run(ctx, f"createdb {dbname}")
    run(ctx, f"ssh {config.host} -C 'pg_dump -Ox {srv_dsn}' | psql {local_dsn}")

    reset_pw(ctx)


@task
def reset_pw(ctx):
    """Set all user passwords to "password" """
    # 'password' encoded with a constant salt. Does not force a login after pull_db
    pw = r"pbkdf2_sha256\$216000\$salt\$xuFh/Jmp9ZyNeO4k67igyjH9t5hHZ84M69rSfrV2W/g="
    run(
        ctx,
        f"venv/bin/python manage.py shell -c \"pw='{pw}';"
        f"from django.contrib.auth import get_user_model as g;"
        f'g()._base_manager.update(password=pw)"',
    )


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
    run(
        ctx,
        "venv/bin/python manage.py makemessages -a --add-location file"
        " -i venv -i htmlcov -i node_modules -i lib",
        replace_env=False,
    )
    run(
        ctx,
        "venv/bin/python manage.py makemessages -a --add-location file"
        " -i venv -i htmlcov -i node_modules -i lib"
        " -d djangojs",
        replace_env=False,
    )


@task
def cm(ctx):
    """Compile the translation catalogs"""
    run(
        ctx,
        "venv/bin/python manage.py compilemessages"
        " -i venv -i htmlcov -i node_modules -i lib",
        replace_env=False,
    )


def _python3():
    interpreters = ("python3.9", "python3.8", "python3.7", "python3.6")
    return next(filter(None, (shutil.which(v) for v in interpreters)))


def _pip_up(c):
    run(c, "venv/bin/python -m pip install -U pip wheel setuptools")


@task(auto_shortflags=False, help={"stable": "Avoid pre-release versions of packages"})
def upgrade(ctx, stable=False):
    """Re-create the virtualenv with newest versions of all libraries"""
    run(ctx, "rm -rf venv")
    run(ctx, f"{_python3()} -m venv venv")
    _pip_up(ctx)
    extra = "" if stable else "--pre"
    run(ctx, f"venv/bin/python -m pip install -U -r requirements-to-freeze.txt {extra}")
    freeze(ctx)


@task
def freeze(ctx):
    """Freeze the virtualenv's state"""
    run(
        ctx,
        '(printf "# AUTOGENERATED, DO NOT EDIT\n\n";' "venv/bin/python -m pip freeze -l"
        # Until Ubuntu gets its act together:
        ' | grep -vE "(^pkg-resources)"' ") > requirements.txt",
    )


@task
def update(ctx):
    """Update virtualenv and node_modules to match the lockfiles"""
    venv = config.base / "venv"
    if not venv.exists():
        run(ctx, f"{_python3()} -m venv venv")
    _pip_up(ctx)
    run(ctx, "venv/bin/python -m pip install -r requirements.txt")
    run(ctx, 'find . -name "*.pyc" -delete')
    run(ctx, "yarn")
    run(ctx, "venv/bin/python manage.py migrate")


def _local_dotenv_if_not_exists():
    dotenv = config.base / ".env"
    if dotenv.exists():
        return

    secret_key = _random_string(50)
    dbname = _dbname_from_domain(config.domain)

    with dotenv.open("w") as f:
        f.write(
            f"""\
DEBUG=True
DATABASE_URL=postgres://localhost:5432/{dbname}
CACHE_URL=hiredis://localhost:6379/1/?key_prefix={dbname}
SECRET_KEY={secret_key}
ALLOWED_HOSTS=["*"]

SENTRY_DSN=
"""
        )


def _local_dbname():
    _local_dotenv_if_not_exists()
    return _dbname_from_dsn(_local_env()("DATABASE_URL"))


@task
def local(ctx):
    """Local environment setup"""
    run(ctx, "rm -rf node_modules venv")
    dbname = _local_dbname()
    run(ctx, f"createdb {dbname}", warn=True)
    update(ctx)


@task
def nine_vhost(ctx):
    """Create a virtual host using nine-manage-vhosts"""
    with Connection(config.host) as conn:
        run(
            conn,
            f"sudo nine-manage-vhosts virtual-host create {config.domain}"
            " --template=feinheit_cache"
            f" --webroot=/home/www-data/{config.domain}/htdocs",
        )
        with conn.cd(config.domain):
            run(conn, "mkdir -p media tmp")


@task(auto_shortflags=False, help={"include-www": "Include the www. subdomain"})
def nine_alias_add(ctx, alias, include_www=False):
    """Add aliasses to a nine-manage-vhost virtual host"""
    with Connection(config.host) as conn:
        run(
            conn,
            f"sudo nine-manage-vhosts alias create --virtual-host={config.domain}"
            f" {alias}",
        )
        if include_www:
            run(
                conn,
                f"sudo nine-manage-vhosts alias create --virtual-host={config.domain}"
                f" www.{alias}",
                warn=True,
            )


@task(auto_shortflags=False, help={"include-www": "Include the www. subdomain"})
def nine_alias_remove(ctx, alias, include_www=False):
    """Remove aliasses from a nine-manage-vhost virtual host"""
    with Connection(config.host) as conn:
        run(
            conn,
            f"sudo nine-manage-vhosts alias remove --virtual-host={config.domain}"
            f" {alias}",
        )
        if include_www:
            run(
                conn,
                f"sudo nine-manage-vhosts alias remove --virtual-host={config.domain}"
                f" www.{alias}",
                warn=True,
            )


@task
def nine_unit(ctx):
    """Start and enable a gunicorn@ unit"""
    with Connection(config.host) as conn:
        run(conn, f"systemctl --user start gunicorn@{config.domain}.service")
        run(conn, f"systemctl --user enable gunicorn@{config.domain}.service")


def _nine_has_manage_databases(conn):
    return bool(run(conn, "which nine-manage-databases", warn=True).stdout.strip())


@task
def nine_db_dotenv(ctx):
    """Create a database and initialize the .env"""
    with Connection(config.host) as conn:
        try:
            conn.get(f"{config.domain}/.env", io.BytesIO())
        except FileNotFoundError:
            pass
        else:
            terminate(f"'{config.domain}/.env' already exists on the server")

        password = _random_string(20, chars="abcdefghijklmnopqrstuvwxyz0123456789")
        secret_key = _random_string(50)
        dbname = _dbname_from_domain(config.domain)

        if _nine_has_manage_databases(conn):
            dbname = f"nmd_{dbname}"
            run(
                conn,
                f"sudo nine-manage-databases database create -t postgresql"
                f' --user={dbname} --password="{password}" {dbname}',
            )

        else:
            run(
                conn,
                f'source ~/.profile && psql -c "CREATE ROLE {dbname} WITH'
                f" ENCRYPTED PASSWORD '{password}'"
                f' LOGIN NOCREATEDB NOCREATEROLE NOSUPERUSER"',
            )
            run(
                conn,
                f'source ~/.profile && psql -c "GRANT {dbname} TO admin"',
            )
            run(
                conn,
                f'source ~/.profile && psql -c "CREATE DATABASE {dbname} WITH'
                f" OWNER {dbname} TEMPLATE template0 ENCODING 'UTF8'"
                f'"',
            )

        conn.put(
            io.StringIO(
                f"""\
DEBUG=False
DATABASE_URL=postgres://{dbname}:{password}@localhost:5432/{dbname}
CACHE_URL=hiredis://localhost:6379/1/?key_prefix={dbname}
SECRET_KEY={secret_key}
ALLOWED_HOSTS=[".{config.domain}", ".{conn.host}"]

GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
SENTRY_DSN=

# LIVE=True
# CANONICAL_DOMAIN={config.domain}
# CANONICAL_DOMAIN_SECURE=True
"""
            ),
            f"{config.domain}/.env",
        )


@task
def nine_ssl(ctx):
    """Activate SSL"""
    with Connection(config.host) as conn:
        run(
            conn,
            f"sudo nine-manage-vhosts certificate create"
            f" --virtual-host={config.domain}",
        )
        run(
            conn,
            f"sudo nine-manage-vhosts virtual-host update"
            f" {config.domain} --template=feinheit_cache_letsencrypt",
        )


@task
def nine_restart(ctx):
    """Restart the application server"""
    with Connection(config.host) as conn:
        with conn.cd(config.domain):
            run(conn, "venv/bin/python manage.py check --deploy")
        run(conn, f"systemctl --user restart gunicorn@{config.domain}.service")


@task
def nine_disable(ctx):
    """Disable a virtual host, dump and remove the DB and stop the gunicorn@ unit"""
    with Connection(config.host) as conn:
        run(conn, f"sudo nine-manage-vhosts virtual-host remove {config.domain}")
        run(conn, f"systemctl --user stop gunicorn@{config.domain}.service")
        run(conn, f"systemctl --user disable gunicorn@{config.domain}.service")

        e = _srv_env(conn, f"{config.domain}/.env")
        srv_dsn = e("DATABASE_URL")
        srv_dbname = _dbname_from_dsn(e("DATABASE_URL"))

        run(conn, f"pg_dump -Ox {srv_dsn} > {config.domain}/{srv_dbname}.sql")

        if _nine_has_manage_databases(conn):
            run(conn, f"sudo nine-manage-databases database drop --force {srv_dbname}")
        else:
            run(conn, f"source ~/.profile && dropdb {srv_dbname}")
            run(conn, f"source ~/.profile && dropuser {srv_dbname}")


@task
def nine_checkout(ctx):
    """Checkout the repository on the server"""
    repo = run(ctx, "git config remote.origin.url", hide=True).stdout.strip()
    with Connection(config.host) as conn:
        run(conn, f"git clone {repo} {config.domain} -b {config.branch}")


@task
def nine_venv(ctx):
    """Create a venv and install packages from requirements.txt"""
    with Connection(config.host) as conn:
        with conn.cd(config.domain):
            run(conn, "rm -rf venv")
            run(conn, "PATH=~/.pyenv/shims:$PATH python3 -m venv venv")
            _pip_up(conn)
            run(conn, "venv/bin/python -m pip install -r requirements.txt")


@task
def nine_reinit_from(ctx, environment):
    """Reinitialize an environment from a different environment"""
    try:
        source = config.environments[environment]
    except KeyError:
        terminate(f'Unknown source environment "{environment}"')

    with Connection(config.host) as conn:
        source_e = _srv_env(conn, f"{config.environments[environment]['domain']}/.env")
        target_e = _srv_env(conn, f"{config.domain}/.env")

        source_dsn = source_e("DATABASE_URL")
        target_dsn = target_e("DATABASE_URL")

        dbname = _dbname_from_dsn(target_dsn)
        run(conn, f'source ~/.profile && psql -c "DROP DATABASE IF EXISTS {dbname}"')
        run(
            conn,
            f'source ~/.profile && psql -c "CREATE DATABASE {dbname} WITH'
            f" OWNER {dbname} TEMPLATE template0 ENCODING 'UTF8'"
            f'"',
        )
        run(conn, f"source ~/.profile && pg_dump -Ox {source_dsn} | psql {target_dsn}")
        run(
            conn,
            f"rsync -aH --stats {source['domain']}/media/ {config.domain}/media/",
        )


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
    username = e("BITBUCKET_USERNAME")
    password = e("BITBUCKET_PASSWORD")
    organization = e("BITBUCKET_ORGANIZATION")
    repository = config.domain

    print(f"Username [{username}]: ", end="")
    username = input() or username
    print(f"Password [{password}]: ", end="")
    password = input() or password
    print(f"Organization [{organization}]: ", end="")
    organization = input() or organization
    print(f"Repository [{repository}]: ", end="")
    repository = input() or repository

    run(
        ctx,
        f"""\
curl -X POST -v -u {username}:"{password}" -H "content-type: application/json"\
 https://api.bitbucket.org/2.0/repositories/{organization}/{repository}\
 -d '{{"scm": "git", "is_private": true, "forking_policy": "no_public_forks"}}'\
""",
    )
    run(ctx, f"git remote add origin git@bitbucket.org:{organization}/{repository}.git")
    run(ctx, f"git push -u origin {config.branch}")


@task
def github(ctx):
    """Create a repository on GitHub and push the code"""
    url = run(ctx, "git config remote.origin.url", hide=True, warn=True).stdout.strip()
    if url:
        terminate(f"The 'origin' remote already points to '{url}'")

    e = _local_env(Path.home() / ".box.env")
    organization = e("GITHUB_ORGANIZATION")
    repository = config.domain

    print(f"Organization [{organization}]: ", end="")
    organization = input() or organization
    print(f"Repository [{repository}]: ", end="")
    repository = input() or repository

    run(ctx, f"gh repo create {organization}/{repository} --private")
    run(ctx, f"git push -u origin {config.branch}")


@task
def fetch(ctx):
    """Ensure a remote exists for the server and fetch"""
    run(
        ctx,
        f"git remote add {config.remote} {config.host}:{config.domain}",
        warn=True,
        hide=True,
    )
    run(ctx, f"git fetch {config.remote}")


def _check_flake8(ctx):
    run(ctx, "pipx run --spec 'flake8>=3.8.3' flake8 .")


def _check_django(ctx):
    run(ctx, "venv/bin/python manage.py check")


def _check_prettier(ctx):
    run(
        ctx,
        f"npx prettier --list-different --no-semi"
        f' "*.js" "{config.app}/static/**/*.js" "{config.app}/static/**/*.scss"',
    )


def _check_eslint(ctx):
    run(ctx, f'npx eslint "*.js" {config.app}/static')


def _check_large_files(ctx, *, limit=500000):
    out = run(
        ctx, "git diff-index --cached --name-only --diff-filter=AMT HEAD", hide=True
    ).stdout.strip()
    sizes = ((f, os.stat(f).st_size) for f in out.splitlines())
    large = {f: size for f, size in sizes if size > limit}
    if large:
        files = ", ".join(
            f"{f} ({size // 1000}kb)"
            for f, size in sorted(large.items(), key=lambda r: r[1])
        )
        terminate(f"Large files detected: {files}")


def _check_branch(ctx):
    branch = run(ctx, "git rev-parse --abbrev-ref HEAD", hide=True).stdout.strip()
    if branch != config.branch:
        terminate(f"Current branch is '{branch}', should be '{config.branch}'")


def _check_no_uncommitted_changes(ctx):
    with Connection(config.host) as conn:
        with conn.cd(config.domain):
            result = run(conn, "git status --porcelain").stdout.strip()
            if result:
                terminate("Terminating because of uncommitted changes on server")


@task
def check(ctx):
    """Check the coding style"""
    _check_flake8(ctx)
    _check_django(ctx)
    _check_prettier(ctx)
    _check_eslint(ctx)
    _check_large_files(ctx)


def _fmt_prettier(ctx):
    run(
        ctx,
        f"npx prettier --write --no-semi"
        f' "*.js" "{config.app}/static/**/*.js" "{config.app}/static/**/*.scss"',
    )


def _fmt_tox_style(ctx):
    run(ctx, "tox -e style")


def _fmt_black(ctx):
    run(ctx, "pipx run --spec 'black>=20.8b1' black .")


def _fmt_isort(ctx):
    run(
        ctx,
        "pipx run --spec 'isort>=5.4' isort"
        " --virtual-env venv --profile=black --lines-after-imports=2 --combine-as"
        " .",
    )


@task
def fmt(ctx):
    """Format the code"""
    _fmt_black(ctx)
    _fmt_isort(ctx)
    _fmt_prettier(ctx)


@task(auto_shortflags=False, help={"fast": "Skip the Webpack build"})
def deploy(ctx, fast=False):
    """Deploy once 🔥"""
    _check_branch(ctx)
    _check_no_uncommitted_changes(ctx)
    check(ctx)
    run(ctx, f"git push origin {config.branch}")
    if not fast:
        run(ctx, "NODE_ENV=production npx webpack -p --bail")

    with Connection(config.host) as conn:
        with conn.cd(config.domain):
            run(conn, f"git checkout {config.branch}")
            run(conn, "git fetch origin")
            run(conn, f"git merge --ff-only origin/{config.branch}")
            run(conn, 'find . -name "*.pyc" -delete')
            _pip_up(conn)
            run(conn, "venv/bin/python -m pip install -r requirements.txt")
            run(conn, "venv/bin/python manage.py migrate")
            run(conn, "venv/bin/python manage.py check --deploy", warn=True)
            if not fast:
                run(
                    ctx,
                    f"rsync -pthrz --delete --stats"
                    f" static/ {config.host}:{config.domain}/static/",
                )
            run(conn, "venv/bin/python manage.py collectstatic --noinput")
        run(conn, f"systemctl --user restart gunicorn@{config.domain}.service")

    fetch(ctx)


GENERAL = {
    hook,
    cm,
    dev,
    mm,
    upgrade,
    freeze,
    update,
    pull_db,
    reset_pw,
    local,
    bitbucket,
    github,
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
    nine_restart,
    nine_disable,
    nine_checkout,
    nine_venv,
    nine_reinit_from,
    nine,
}
