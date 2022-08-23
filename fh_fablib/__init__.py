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
from speckenv_django import django_database_url

from fh_fablib.extract_js_gettext_strings import generate_strings


__version__ = "1.0.20220824"


# I don't care, in this context.
warnings.simplefilter("ignore", category=ResourceWarning)


def ansi(code):
    return lambda s: f"\033[{code}m{s}\033[0m"


# underline = ansi("4")
red = ansi("31")
green = ansi("32")
purple = ansi("35")


def progress(msg):
    print(green(msg))


def info(msg):
    print(purple(msg))


def terminate(msg):
    print(red(msg), file=sys.stderr)
    sys.exit(1)


def require(version):
    if __version__ < version:
        terminate(f"fh_fablib version {version} required (you have {__version__})")
    if __version__ > version:
        path = Path.cwd() / "fabfile.py"
        if path.is_file() and (old := path.read_text()):
            new = "".join(
                f'fl.require("{__version__}")\n'
                if line.startswith("fl.require")
                else line
                for line in old.splitlines(keepends=True)
            )
            if new != old:
                path.write_text(new)
                info(
                    "The fabfile has been updated automatically with your"
                    " local fh_fablib version."
                )
                return

        info(f"fh_fablib version is {__version__}, project requires only {version}.")


def run(c, *a, **kw):
    """A Context.run or Connection.run with better defaults"""
    kw.setdefault("echo", True)
    kw.setdefault("pty", True)
    kw.setdefault("replace_env", False)
    return c.run(*a, **kw)


class Config:
    app = "app"
    environment = "default"
    environments = {}
    force = False

    def update(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)

        os.chdir(self.base)

    def __getattr__(self, key):
        environments = getattr(self, "environments", None)
        if environments:
            environments = f" [{', '.join(environments)}]"
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
        cfg["environment"] = name
        config.update(**cfg)

    fn.__doc__ = f'Set the environment to "{name}"'
    return fn


class Connection(Connection):
    """Connection subclass which always forwards the agent by default"""

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("forward_agent", True)
        super().__init__(*args, **kwargs)


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

set -ex
{jobs}
{{ set +x; }} 2>/dev/null

for job in $(jobs -p); do wait $job; done
"""
        )
        f.flush()
        run(ctx, f"bash {f.name}", replace_env=False)


@task(auto_shortflags=False, help={"force": "Overwrite existing pre-commit files"})
def hook(ctx, force=False):
    """
    Add default pre-commit configuration and install hook running coding style checks
    """
    source = Path(__file__).parent / "dotfiles"
    target = config.base
    for s in sorted(source.glob("*")):
        t = target / s.name
        if force or not t.exists():
            shutil.copy(s, t)
            info(f"Copying {s.name} into project...")
    run(ctx, "pre-commit install -f")


@task(auto_shortflags=False)
def dev(ctx, host="127.0.0.1", port=8000):
    """Run the development server for the frontend and backend"""
    progress(f"Starting server at http://{host}:{port}/")
    backend = random.randint(50000, 60000)
    _concurrently(
        ctx,
        [
            f"venv/bin/python manage.py runserver {backend}",
            f"yarn run webpack serve --hot --host {host} --port {port} --env backend={backend}",
        ],
    )


def _old_dev(ctx, host="127.0.0.1", port=8000):
    _concurrently(
        ctx,
        [
            f"venv/bin/python manage.py runserver 0.0.0.0:{port}",
            f'HOST="{host}" yarn run webpack-dev-server --host 0.0.0.0 --port 4000 --hot',
        ],
    )


@task(auto_shortflags=False)
def pull_db(ctx, extra_dump_args=""):
    """Pull a local copy of the remote DB and reset all passwords"""
    _local_dotenv_if_not_exists()

    with Connection(config.host) as conn:
        e = _srv_env(conn, f"{config.domain}/.env")

    srv_dsn = e("DATABASE_URL")
    local_dsn = _local_env()("DATABASE_URL")
    dbname = _dbname_from_dsn(local_dsn)

    run(ctx, f"dropdb --if-exists {dbname}", warn=True)
    run(ctx, f"createdb {dbname}")
    run(
        ctx,
        f"ssh {config.host} -C 'pg_dump -Ox {srv_dsn} {extra_dump_args}' | psql {local_dsn}",
    )

    reset_pw(ctx)


@task(auto_shortflags=False)
def pull_media(ctx, folder="media"):
    """Rsync a folder from the remote to the local environment"""
    flags = "-pthrz --stats"
    folder = folder.strip("/")
    run(ctx, f"rsync {flags} {config.host}:{config.domain}/{folder}/ {folder}/")


@task
def reset_pw(ctx):
    """Set all user passwords to "password" """
    # 'password' encoded with a constant salt. Does not force a login after pull_db
    pw = r"pbkdf2_sha256\$320000\$2Hz1pcncCTWtqEnr3uoBdD\$nVc9Fka1oYQHFgGRGLUC4Nw3w6+ZmdO0IDdZOow+kJ0="
    run(
        ctx,
        f"venv/bin/python manage.py shell -c \"pw='{pw}';"
        f"from django.contrib.auth import get_user_model as g;"
        f'g()._base_manager.update(password=pw)"',
    )


@task
def reset_sq(ctx):
    """Reset all PostgreSQL sequences"""

    SQL = """
SELECT 'SELECT SETVAL(' ||
       quote_literal(quote_ident(PGT.schemaname) || '.' || quote_ident(S.relname)) ||
       ', COALESCE(MAX(' ||quote_ident(C.attname)|| '), 1) ) FROM ' ||
       quote_ident(PGT.schemaname)|| '.'||quote_ident(T.relname)|| ';'
FROM pg_class AS S,
     pg_depend AS D,
     pg_class AS T,
     pg_attribute AS C,
     pg_tables AS PGT
WHERE S.relkind = 'S'
    AND S.oid = D.objid
    AND D.refobjid = T.oid
    AND D.refobjid = C.attrelid
    AND D.refobjsubid = C.attnum
    AND T.relname = PGT.tablename
ORDER BY S.relname;
    """

    dsn = _local_env()("DATABASE_URL")

    with tempfile.NamedTemporaryFile("w") as f:
        f.write(SQL)
        f.seek(0)
        run(ctx, f"psql -Atq -f {f.name} {dsn} | psql -a {dsn}")


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


@task(
    auto_shortflags=False,
    help={"language": "Generate catalogs for a specific language"},
)
def mm(ctx, language=None):
    """Update the translation catalogs"""

    with open("conf/strings.js", "w", encoding="utf-8") as f:
        f.write("/* eslint-disable */\n")
        f.write("".join(f"{str}\n" for str in generate_strings()))

    language = f"-l {language}" if language else "-a"
    run(
        ctx,
        f"venv/bin/python manage.py makemessages {language} --add-location file"
        " -i venv -i htmlcov -i node_modules -i lib -i build -i dist --no-wrap",
        replace_env=False,
    )
    run(
        ctx,
        f"venv/bin/python manage.py makemessages {language} --add-location file"
        " -i venv -i htmlcov -i node_modules -i lib -i build -i dist --no-wrap"
        " -d djangojs",
        replace_env=False,
    )


@task
def cm(ctx):
    """Compile the translation catalogs"""
    run(
        ctx,
        "venv/bin/python manage.py compilemessages"
        " -i venv -i htmlcov -i node_modules -i lib -i build -i dist",
        replace_env=False,
    )


def _python3():
    interpreters = ("python3.10", "python3.9", "python3.8")
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
    hook(ctx)


@task
def freeze(ctx):
    """Freeze the virtualenv's state"""
    run(
        ctx,
        '(printf "# AUTOGENERATED, DO NOT EDIT\n\n";' "venv/bin/python -m pip freeze -l"
        # Until Ubuntu gets its act together:
        ' | grep -vE "(^pkg.resources)"' ") > requirements.txt",
    )


@task
def update(ctx):
    """Update virtualenv and node_modules to match the lockfiles"""
    venv = config.base / "venv"
    if not venv.exists():
        run(ctx, f"{_python3()} -m venv venv")
    _pip_up(ctx)
    run(ctx, "venv/bin/python -m pip install -r requirements.txt")
    run(ctx, "git submodule update --init")
    run(ctx, 'find . -name "*.pyc" -delete')
    run(ctx, "yarn")
    run(ctx, "venv/bin/python manage.py migrate", warn=True)
    hook(ctx)


def _local_dotenv_if_not_exists():
    dotenv = config.base / ".env"
    if dotenv.exists():
        return

    secret_key = _random_string(70)
    dbname = _dbname_from_domain(config.domain)

    with dotenv.open("w") as f:
        f.write(
            f"""\
DEBUG=True
DATABASE_URL=postgres://localhost:5432/{dbname}
CACHE_URL=hiredis://localhost:6379/1/?key_prefix={dbname}
SECRET_KEY={secret_key}
ALLOWED_HOSTS=["*", ".localhost"]

SENTRY_DSN=
SENTRY_ENVIRONMENT=
"""
        )


def _local_dbname():
    _local_dotenv_if_not_exists()
    return _dbname_from_dsn(_local_env()("DATABASE_URL"))


@task(
    auto_shortflags=False,
    help={"clobber": "Clobber pre-existing node_modules and venv folders"},
)
def local(ctx, clobber=False):
    """Local environment setup"""
    if clobber:
        run(ctx, "rm -rf node_modules venv")
    dbname = _local_dbname()
    run(ctx, f"createdb {dbname}", warn=True)
    update(ctx)


@task
def nine_vhost(ctx):
    """Create a virtual host using nine-manage-vhosts"""
    with Connection(config.host) as conn, conn.cd(config.domain):
        run(
            conn,
            f"sudo nine-manage-vhosts virtual-host create {config.domain}"
            " --template=feinheit_cache"
            f" --webroot=/home/www-data/{config.domain}/htdocs",
        )
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
        run(conn, f"systemctl --user enable --now gunicorn@{config.domain}.service")


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
        secret_key = _random_string(70)
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
ALLOWED_HOSTS=[".{config.domain}", ".{conn.host}", ".feinheit.dev"]

GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=

SENTRY_DSN=
SENTRY_ENVIRONMENT=

# LIVE=True
# SECURE_SSL_HOST={config.domain}
# SECURE_SSL_REDIRECT=True
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


def _nine_restart(conn):
    run(conn, f"systemctl --user restart gunicorn@{config.domain}.service")


@task
def nine_restart(ctx):
    """Restart the application server"""
    with Connection(config.host) as conn, conn.cd(config.domain):
        run(conn, "venv/bin/python manage.py check --deploy")
        _nine_restart(conn)


@task
def nine_disable(ctx):
    """Disable a virtual host, dump and remove the DB and stop the gunicorn@ unit"""
    with Connection(config.host) as conn:
        run(conn, f"sudo nine-manage-vhosts virtual-host remove {config.domain}")
        run(conn, f"systemctl --user disable --now gunicorn@{config.domain}.service")

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


@task(
    auto_shortflags=False,
    help={"python3": "Python executable"},
)
def nine_venv(ctx, python3="python3"):
    """Create a venv and install packages from requirements.txt"""
    with Connection(config.host) as conn, conn.cd(config.domain):
        run(conn, "rm -rf venv")
        run(conn, f"PATH=~/.pyenv/shims:$PATH {python3} -m venv venv")
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

        run(conn, f"pg_dump -Ox {target_dsn} > {config.domain}/tmp/{dbname}.sql")

        if _nine_has_manage_databases(conn):
            password = django_database_url(target_dsn)["PASSWORD"]
            run(
                conn,
                f"sudo nine-manage-databases database drop -t postgresql {dbname} --force",
            )
            run(
                conn,
                f'sudo nine-manage-databases database create -t postgresql --user={dbname} --password="{password}" {dbname}',
            )

        else:
            run(
                conn, f'source ~/.profile && psql -c "DROP DATABASE IF EXISTS {dbname}"'
            )
            run(
                conn,
                f'source ~/.profile && psql -c "CREATE DATABASE {dbname} WITH'
                f" OWNER {dbname} TEMPLATE template0 ENCODING 'UTF8'"
                f'"',
            )

        run(conn, f"pg_dump -Ox {source_dsn} | psql {target_dsn}")
        run(
            conn,
            f"rsync -aH --stats {source['domain']}/media/ {config.domain}/media/",
        )
    progress(f"Success! (A database backup is at {config.domain}/tmp/)")
    progress("You may have to run nine-restart or even deploy once.")


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


def _check_branch(ctx):
    branch = run(ctx, "git rev-parse --abbrev-ref HEAD", hide=True).stdout.strip()
    if branch != config.branch:
        terminate(f"Current branch is '{branch}', should be '{config.branch}'")


def _check_no_uncommitted_changes(ctx):
    with Connection(config.host) as conn, conn.cd(config.domain):
        result = run(conn, "git status --porcelain").stdout.strip()
        if result:
            terminate("Terminating because of uncommitted changes on server")


@task
def check(ctx):
    """Check the coding style of staged files"""
    run(ctx, "pre-commit run")


def _deploy_sync_origin_url(ctx, conn):
    url = run(ctx, "git remote get-url origin").stdout.strip()
    run(conn, f"git remote set-url origin {url}")


def _deploy_django(conn):
    run(conn, "git fetch origin")
    run(conn, f"git checkout {config.branch}")

    result = run(conn, "git status --porcelain").stdout.strip()
    if result:
        terminate("Terminating because of uncommitted changes on server")

    run(conn, f"git reset --hard origin/{config.branch}")
    run(conn, "git submodule update --init")
    run(conn, 'find . -name "*.pyc" -delete')
    _pip_up(conn)
    run(conn, "venv/bin/python -m pip install -r requirements.txt")
    run(conn, "venv/bin/python manage.py migrate")
    run(conn, "venv/bin/python manage.py check --deploy", warn=True)


def _deploy_staticfiles(conn):
    run(conn, "venv/bin/python manage.py collectstatic --noinput")


def _rsync_static(ctx, *, delete=False):
    flags = "-pthrz --stats"
    delete = " --delete" if delete else ""
    run(ctx, f"rsync {flags}{delete} static/ {config.host}:{config.domain}/static/")


@task(
    auto_shortflags=False,
    help={"fast": "Skip the Webpack build", "force": "Force the git push"},
)
def deploy(ctx, fast=False, force=False):
    """Deploy once 🔥"""
    _check_branch(ctx)
    _check_no_uncommitted_changes(ctx)
    check(ctx)
    force = "--force-with-lease " if (force or config.force) else ""
    run(ctx, f"git push origin {force}{config.branch}")
    if not fast:
        run(ctx, "NODE_ENV=production yarn run webpack --mode production --bail")

    with Connection(config.host) as conn, conn.cd(config.domain):
        _deploy_sync_origin_url(ctx, conn)
        _deploy_django(conn)
        if not fast:
            _rsync_static(ctx, delete=True)
        _deploy_staticfiles(conn)
        _nine_restart(conn)

    fetch(ctx)
    progress(f"Successfully deployed the {config.environment} environment.")


GENERAL = {
    hook,
    cm,
    dev,
    mm,
    upgrade,
    freeze,
    update,
    pull_db,
    pull_media,
    reset_pw,
    reset_sq,
    local,
    bitbucket,
    github,
    fetch,
    check,
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
