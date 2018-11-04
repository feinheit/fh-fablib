from __future__ import unicode_literals

import socket
import subprocess
import tempfile

from fabric.api import env, hosts, task
from fabric.colors import green
from fabric.utils import puts

from fh_fablib import run_local, require_services


def own_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.connect(("feinheit.ch", 80))
    return s.getsockname()[0]


@task(default=True)
@hosts("")
@require_services
def dev(host="127.0.0.1", port=8000):
    """Runs the development server, SCSS watcher and backend services if they
    are not running already"""
    if host == "net":
        host = own_ip()

    puts(green("Starting dev server on http://%s:%s/" % (host, port), bold=True))

    with tempfile.NamedTemporaryFile() as f:
        # https://gist.github.com/jiaaro/b2e1b7c705022c2cf56888152a999f65
        f.write(
            """\
trap "exit" INT TERM
trap "kill 0" EXIT

venv/bin/python -Wonce manage.py runserver 0.0.0.0:%(port)s &
HOST=%(host)s yarn run dev &

for job in $(jobs -p); do wait $job; done
"""
            % {"port": port, "host": host}
        )
        f.flush()

        run_local("bash %s" % f.name)


@task
@hosts("")
def mm(language=None):
    """Wrapper around the ``makemessages`` management command which excludes
    dependencies (virtualenv, bower components, node modules)"""
    run_local(
        " ".join(
            [
                "venv/bin/python manage.py makemessages",
                ("-l %s" % language) if language else "-a",
                "-i app/cms",
                "-i bower_components",
                "-i node_modules",
                "-i venv",
            ]
        )
    )

    """Also statici18n ``makemessages`` command will be executed"""
    run_local(
        " ".join(
            [
                "venv/bin/python manage.py makemessages -d djangojs",
                ("-l %s" % language) if language else "-a",
                "-e jsx,js",
                "-i app/static/jsi18n",
                "-i app/cms",
                "-i app/templates/elephantblog",
                "-i bower_components",
                "-i node_modules",
                "-i venv",
            ]
        )
    )


@task
@hosts("")
def cm():
    """Wrapper around ``compilemessages`` which does not descend into
    venv"""
    run_local(
        ". venv/bin/activate && for dir in "
        "$(find . -name venv -prune -or -name locale -print)"
        "; do (cd $dir; cd ..; django-admin.py compilemessages); done"
    )


@task
@hosts("")
@require_services
def services():
    """Starts all required background services"""
    pass


@task
@hosts("")
def kill():
    """Send SIGTERM to postgres and redis-server"""
    subprocess.call(
        "ps -ef | awk '/(postgres|redis)/ {print $2}' | xargs kill", shell=True
    )


@task(aliases=["prettier"])
@hosts("")
def prettify():
    """Prettifies JS and SCSS code using prettier"""
    for cmd in env["box_prettify"]:
        run_local(cmd)


@task
@hosts("")
def optimize():
    """Optimizes SVG, PNG and JPEG files with svgo and imagemagick (convert)"""
    for cmd in env["box_optimize"]:
        run_local(cmd)
