from __future__ import unicode_literals

from multiprocessing import Process
import os
import socket
import subprocess

from fabric.api import env, hosts, task
from fabric.colors import green
from fabric.utils import puts

from fh_fablib import run_local, require_services


def own_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.connect(('feinheit.ch', 80))
    return s.getsockname()[0]


@task(default=True)
@hosts('')
@require_services
def dev(host='127.0.0.1', port=8000):
    """Runs the development server, SCSS watcher and backend services if they
    are not running already"""
    if host == 'net':
        host = own_ip()
        puts(green(
            'Starting dev server on http://%s:%s/' % (host, port),
            bold=True))

    jobs = [
        lambda: run_local(
            'venv/bin/python -Wonce manage.py runserver %s:%s' % (
                host,
                port,
            ),
        ),
    ]
    if os.path.exists('gulpfile.js'):
        jobs.append(lambda: run_local('./node_modules/.bin/gulp'))
    elif os.path.exists('%(box_staticfiles)s/Gruntfile.js' % env):
        jobs.append(lambda: run_local('cd %(box_sass)s && grunt'))
    elif os.path.exists('%(box_staticfiles)s/config.rb' % env):
        jobs.append(
            lambda: run_local('bundle exec compass watch %(box_staticfiles)s'))
    elif os.path.exists('%(box_staticfiles)s/webpack.config.js' % env):
        jobs.append(
            lambda: run_local(
                './node_modules/.bin/webpack -d --watch'
                ' --config %(box_staticfiles)s/webpack.config.js'))
    elif os.path.exists('server.js'):
        jobs.append(lambda: run_local('HOST=%s node server' % host))
    elif os.path.exists('postcss.config.js'):  # Just a marker...
        jobs.append(lambda: run_local('HOST=%s npm run dev' % host))

    jobs = [Process(target=j) for j in jobs]
    [j.start() for j in jobs]
    [j.join() for j in jobs]


@task
@hosts('')
def makemessages():
    """Wrapper around the ``makemessages`` management command which excludes
    dependencies (virtualenv, bower components, node modules)"""
    run_local(
        'venv/bin/python manage.py makemessages -a'
        ' -i app/cms'
        ' -i bower_components'
        ' -i node_modules'
        ' -i venv')

    """Also statici18n ``makemessages`` command will be executed"""
    run_local(
        'venv/bin/python manage.py makemessages -d djangojs -a'
        ' -e jsx,js'
        ' -i app/static/jsi18n'
        ' -i app/cms'
        ' -i app/templates/elephantblog'
        ' -i bower_components'
        ' -i node_modules'
        ' -i venv')


@task
@hosts('')
def compilemessages():
    """Wrapper around ``compilemessages`` which does not descend into
    venv"""
    run_local(
        '. venv/bin/activate && for dir in '
        '$(find . -name venv -prune -or -name locale -print)'
        '; do (cd $dir; cd ..; django-admin.py compilemessages); done')


@task
@hosts('')
@require_services
def services():
    """Starts all required background services"""
    pass


@task
@hosts('')
def kill():
    """Send SIGTERM to postgres and redis-server"""
    subprocess.call(
        "ps -ef | awk '/(postgres|redis)/ {print $2}' | xargs kill",
        shell=True)
