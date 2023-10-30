import inspect
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
from invoke import Collection  # noqa: F401
from speckenv_django import django_database_url

from fh_fablib.extract_js_gettext_strings import generate_strings


__version__ = "1.0.20231030"


# I don't care, in this context.
warnings.simplefilter("ignore", category=ResourceWarning)


def ansi(code):
    return lambda s: f"\033[{code}m{s}\033[0m"


# underline = ansi("4")
red = ansi("31")
green = ansi("32")
yellow = ansi("33")
magenta = ansi("35")


def progress(msg):
    print(green(msg))


def info(msg):
    print(magenta(msg))


def warning(msg):
    print(yellow(msg))


def terminate(msg):
    print(red(msg), file=sys.stderr)
    sys.exit(1)


def _bool(s):
    true = {"yes", "true"}
    false = {"no", "false"}
    if s in true:
        return True
    elif s in false:
        return False
    terminate(
        f"Boolean argument value {s!r} not recognized. Use yes, true, no or false."
    )


def _find_base():
    frame = inspect.currentframe().f_back.f_back
    try:
        while frame:
            if (name := frame.f_locals.get("__file__")) and name.endswith(
                "/fabfile.py"
            ):
                return Path(name).parent
            frame = frame.f_back
    finally:
        del frame


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
                _update_dotfiles(force=True)
                warning(
                    "The fabfile and dotfiles have been updated automatically.\n\nPlease check the result twice before committing!"
                )


def run(c, *a, **kw):
    """A Context.run or Connection.run with better defaults"""
    kw.setdefault("pty", False)
    kw.setdefault("replace_env", True)
    if not kw.get("hide"):
        progress(" ".join(str(part) for part in a))
    return c.run(*a, **kw)


def run_local(c, *a, **kw):
    """A Context.run for local execution with better defaults"""
    kw.setdefault("pty", True)
    kw.setdefault("replace_env", False)
    if not kw.get("hide"):
        progress(" ".join(str(part) for part in a))
    return c.run(*a, **kw)


class Config:
    def update(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)
            os.environ[f"FL_{key.upper()}"] = str(value)

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
config.update(
    base=_find_base(),
    environment="default",
    environments={},
    force=False,
)
os.chdir(config.base)


def environment(name, cfg, **kwargs):
    config.environments[name] = cfg

    if name in kwargs.get("aliases", ()):
        terminate(f"Remove {name} from the aliases list of the {name} environment.")

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
        run_local(ctx, f"bash {f.name}", replace_env=False)


def _update_dotfiles(*, force):
    source = Path(__file__).parent / "dotfiles"
    target = config.base
    for s in sorted(source.glob("*")):
        t = target / s.name
        if force or not t.exists():
            shutil.copy(s, t)


@task(auto_shortflags=False, help={"force": "Overwrite existing pre-commit files"})
def hook(ctx, force=False):
    """
    Add default pre-commit configuration and install hook running coding style checks
    """
    _update_dotfiles(force=force)
    run_local(ctx, "pre-commit install -f")


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

    run_local(ctx, f"dropdb --if-exists {dbname}", warn=True)
    run_local(ctx, f"createdb {dbname}")
    run_local(
        ctx,
        f"ssh {config.host} -C 'pg_dump -Ox {srv_dsn} {extra_dump_args}' | psql {local_dsn}",
    )

    reset_pw(ctx)


@task(auto_shortflags=False)
def pull_media(ctx, folder="media"):
    """Rsync a folder from the remote to the local environment"""
    flags = "-pthrz --stats"
    folder = folder.strip("/")
    run_local(ctx, f"rsync {flags} {config.host}:{config.domain}/{folder}/ {folder}/")


@task
def reset_pw(ctx):
    """Set all user passwords to "password" """
    # 'password' encoded with a constant salt. Does not force a login after pull_db
    pw = r"pbkdf2_sha256\$320000\$2Hz1pcncCTWtqEnr3uoBdD\$nVc9Fka1oYQHFgGRGLUC4Nw3w6+ZmdO0IDdZOow+kJ0="
    run_local(
        ctx,
        f"venv/bin/python manage.py shell -c \"pw='{pw}';"
        f"from django.contrib.auth import get_user_model as g;"
        f'g()._base_manager.update(password=pw)"',
    )


@task
def reset_sq(ctx):
    """Reset all PostgreSQL sequences"""

    sql = """
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
        f.write(sql)
        f.seek(0)
        run_local(ctx, f"psql -Atq -f {f.name} {dsn} | psql -a {dsn}")


def _local_env(path=".env"):
    mapping = {}
    speckenv.read_speckenv(config.base / path, mapping=mapping)

    return lambda *a, **kw: speckenv.env(*a, **kw, mapping=mapping)


def _srv_env(conn, path):
    mapping = {}

    with tempfile.NamedTemporaryFile() as f:
        try:
            conn.get(path, f.name)
        except OSError as exc:
            terminate(f"Unable to read {conn.host}:{path}: {exc}")

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
        f.write("".join(f"{string}\n" for string in generate_strings()))

    language = f"-l {language}" if language else "-a"
    run_local(
        ctx,
        f"venv/bin/python manage.py makemessages {language} --add-location file"
        " -i venv -i htmlcov -i node_modules -i lib -i build -i dist --no-wrap",
        replace_env=False,
    )
    run_local(
        ctx,
        f"venv/bin/python manage.py makemessages {language} --add-location file"
        " -i venv -i htmlcov -i node_modules -i lib -i build -i dist --no-wrap"
        " -d djangojs",
        replace_env=False,
    )


@task
def cm(ctx):
    """Compile the translation catalogs"""
    run_local(
        ctx,
        "venv/bin/python manage.py compilemessages"
        " -i venv -i htmlcov -i node_modules -i lib -i build -i dist",
        replace_env=False,
    )


def _python3():
    interpreters = ("python3.11", "python3.10", "python3.9", "python3.8")
    return next(filter(None, (shutil.which(v) for v in interpreters)))


def _pip_up(c):
    run(c, "venv/bin/python -m pip install -U pip wheel setuptools")


@task(
    auto_shortflags=False,
    help={
        "keep": "Keep the existing virtualenv",
        "stable": "Avoid pre-release versions of packages",
    },
)
def upgrade(ctx, keep=False, stable=False):
    """Re-create the virtualenv with newest versions of all libraries"""
    venv = config.base / "venv"
    if not venv.exists() or not keep:
        run_local(ctx, f"rm -rf venv && {_python3()} -m venv venv")
    _pip_up(ctx)
    extra = "" if stable else "--pre"
    run_local(
        ctx, f"venv/bin/python -m pip install -U -r requirements-to-freeze.txt {extra}"
    )
    freeze(ctx)
    hook(ctx)


@task
def freeze(ctx):
    """Freeze the virtualenv's state"""
    run_local(
        ctx,
        '(printf "# AUTOGENERATED, DO NOT EDIT\n\n";'
        "venv/bin/python -m pip freeze -l"
        # Until Ubuntu gets its act together:
        ' | grep -vE "(^pkg.resources)"'
        ") > requirements.txt",
    )


@task
def update(ctx):
    """Update virtualenv and node_modules to match the lockfiles"""
    venv = config.base / "venv"
    if not venv.exists():
        run_local(ctx, f"{_python3()} -m venv venv")
    _pip_up(ctx)
    _concurrently(
        ctx,
        [
            "venv/bin/python -m pip install -r requirements.txt",
            "git submodule update --init",
            'find . -name "*.pyc" -delete',
            "yarn",
        ],
    )
    run_local(ctx, "venv/bin/python manage.py migrate", warn=True)
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
        run_local(ctx, "rm -rf node_modules venv")
    dbname = _local_dbname()
    run_local(ctx, f"createdb {dbname}", warn=True)
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
def nine_alias_add(ctx, alias, include_www):
    """Add aliasses to a nine-manage-vhost virtual host"""
    include_www = _bool(include_www)
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
def nine_alias_remove(ctx, alias, include_www):
    """Remove aliasses from a nine-manage-vhost virtual host"""
    include_www = _bool(include_www)
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


def _unit(config, *, args=""):
    # args = " -w 2 --preload"
    return f"""\
[Unit]
Description=gunicorn for {config.domain}

[Service]
Environment=LANG=en_US.UTF-8 LC_ALL=en_US.UTF-8 LC_CTYPE=en_US.UTF-8
ExecStart=/home/www-data/{config.domain}/venv/bin/gunicorn wsgi:application -b unix:///home/www-data/{config.domain}/tmp/gunicorn.sock --max-requests 1000 --max-requests-jitter 100 {args}
SyslogIdentifier=gunicorn:{config.domain}
WorkingDirectory=/home/www-data/{config.domain}/
Restart=always

[Install]
WantedBy=default.target
"""


@task
def nine_unit(ctx):
    """Start and enable a gunicorn unit"""
    with Connection(config.host) as conn:
        conn.put(
            io.StringIO(_unit(config)), f".config/systemd/user/{config.domain}.service"
        )
        run(conn, "systemctl --user daemon-reload")
        run(conn, f"systemctl --user enable --now {config.domain}.service")

    info("Successfully created the virtual host.\n")
    warning("Please update the hostings overview as well!")


def _nine_has_manage_databases(conn):
    return bool(run(conn, "which nine-manage-databases", warn=True).stdout.strip())


@task(
    auto_shortflags=False,
    help={"recreate": "Only recreate the database"},
)
def nine_db_dotenv(ctx, recreate=False):
    """Create a database and initialize the .env"""
    with Connection(config.host) as conn:
        if recreate:
            e = _srv_env(conn, f"{config.domain}/.env")
            db = django_database_url(e("DATABASE_URL", required=True))

            password = db["PASSWORD"]
            dbname = db["NAME"]
        else:
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

        if not recreate:
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
    run(conn, f"systemctl --user restart {config.domain}.service")


@task
def nine_restart(ctx):
    """Restart the application server"""
    with Connection(config.host) as conn, conn.cd(config.domain):
        run(conn, "venv/bin/python manage.py check --deploy")
        _nine_restart(conn)


@task
def nine_disable(ctx):
    """Disable a virtual host, dump and remove the DB and stop the gunicorn unit"""
    with Connection(config.host) as conn:
        run(conn, f"sudo nine-manage-vhosts virtual-host remove {config.domain}")

        run(conn, f"systemctl --user disable --now {config.domain}.service")
        run(conn, f"rm -f .config/systemd/user/{config.domain}.service")
        run(conn, "systemctl --user daemon-reload")

        e = _srv_env(conn, f"{config.domain}/.env")
        srv_dsn = e("DATABASE_URL")
        srv_dbname = _dbname_from_dsn(e("DATABASE_URL"))

        run(conn, f"pg_dump -Ox {srv_dsn} > {config.domain}/{srv_dbname}.sql")

        if _nine_has_manage_databases(conn):
            run(conn, f"sudo nine-manage-databases database drop --force {srv_dbname}")
        else:
            run(conn, f"source ~/.profile && dropdb {srv_dbname}")
            run(conn, f"source ~/.profile && dropuser {srv_dbname}")

    info("Successfully removed the virtual host.\n")
    warning("Please update the hostings overview as well!")


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
        media_source = f"{source['domain']}/media/"
        media_target = f"{config.domain}/media/"
        run(
            conn,
            f"rsync -aH --stats --link-dest=`pwd`/{media_source} {media_source} {media_target}",
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


@task
def github(ctx):
    """Create a repository on GitHub and push the code"""
    url = run_local(
        ctx, "git config remote.origin.url", hide=True, warn=True
    ).stdout.strip()
    if url:
        terminate(f"The 'origin' remote already points to '{url}'")

    e = _local_env(Path.home() / ".box.env")
    organization = e("GITHUB_ORGANIZATION")
    repository = config.domain

    print(f"Organization [{organization}]: ", end="")
    organization = input() or organization
    print(f"Repository [{repository}]: ", end="")
    repository = input() or repository

    run_local(
        ctx,
        f"gh repo create {organization}/{repository} --private --source=. --remote=origin --push",
    )
    run_local(ctx, f"git push -u origin {config.branch}")


@task
def fetch(ctx):
    """Ensure a remote exists for the server and fetch"""
    run_local(
        ctx,
        f"git remote add {config.remote} {config.host}:{config.domain}",
        warn=True,
        hide=True,
    )
    run_local(ctx, f"git fetch {config.remote}")


def _check_branch(ctx):
    branch = run_local(ctx, "git rev-parse --abbrev-ref HEAD", hide=True).stdout.strip()
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
    run_local(ctx, "pre-commit run")


def _deploy_sync_origin_url(ctx, conn):
    url = run_local(ctx, "git remote get-url origin").stdout.strip()
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
    run_local(
        ctx, f"rsync {flags}{delete} static/ {config.host}:{config.domain}/static/"
    )


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
    run_local(ctx, f"git push origin {force}{config.branch}")
    if not fast:
        run_local(ctx, "NODE_ENV=production yarn run webpack --mode production --bail")

    with Connection(config.host) as conn, conn.cd(config.domain):
        _deploy_sync_origin_url(ctx, conn)
        _deploy_django(conn)
        if not fast:
            run(
                conn,
                "if [ -e static ]; then find static/ -type f -mtime +60 -delete;fi",
            )
            _rsync_static(ctx, delete=False)
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
