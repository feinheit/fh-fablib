from __future__ import unicode_literals

from functools import wraps
from os import chmod, mkdir, getuid
from os.path import dirname, exists, join
import socket
from subprocess import Popen, PIPE, call
import time
import pwd

from fabric.api import env, cd, run, local as run_local, task
from fabric.colors import cyan, red
from fabric.contrib.console import confirm
from fabric.utils import abort, puts


VERSION = (0, 2, 1)
__version__ = '.'.join(map(str, VERSION))


def require_env(fn):
    @wraps(fn)
    def _dec(*args, **kwargs):
        # box_remote is as good as any value being set from the
        # environment dictionary
        if not env.get('box_remote'):
            abort(red(
                'Environment (one of %s) missing. "fab <env> <command>"'
                % ', '.join(env.box_environments.keys()), bold=True))
        return fn(*args, **kwargs)
    return _dec


def require_services(fn):
    def _service(port, executable, delay):
        try:
            socket.create_connection(
                ('localhost', port),
                timeout=0.1).close()
        except socket.error:
            step('Launching %s in the background...' % executable)
            call('%(executable)s &> tmp/%(executable)s.log &' % {
                'executable': executable,
            }, shell=True)
            time.sleep(delay)

            try:
                socket.create_connection(
                    ('localhost', port),
                    timeout=0.1).close()
            except socket.error:
                abort(red('Unable to start %s!' % executable, bold=True))

    @wraps(fn)
    def _dec(*args, **kwargs):
        _service(5432, 'postgres', 0.5)
        _service(6379, 'redis-server', 0.1)
        return fn(*args, **kwargs)
    return _dec


# Progress ------------------------------------------------------------------

def step(str):
    puts(cyan('\n%s' % str, bold=True))


def init(fabfile, min_version=None):
    if min_version is not None:
        if VERSION < min_version:
            abort(red(
                'fh-fablib update required. Have: %s. Want: %s.' % (
                    '.'.join(map(str, VERSION)),
                    '.'.join(map(str, min_version)),
                ),
            ))

    fabfile['__all__'] = (
        'check',
        'deploy',
        'dev',
        'git',
        'local',
        'server',
    )

    if pwd.getpwuid(getuid())[0] == 'www-data':
        abort(red('Stop fab-ing on the server.', bold=True))

    # Multi-env support ------------------------------------------------------

    def _create_setup_task_for_env(environment):
        def _setup():
            env['box_environment'] = environment
            for key, value in env.box_environments[environment].items():
                env['box_%s' % key] = value
            env.hosts = env.box_servers
        _setup.__name__ = str(environment)
        _setup.__doc__ = 'Set environment to %s' % environment
        return _setup

    if env.get('box_hardwired_environment'):
        _create_setup_task_for_env(env.box_hardwired_environment)()

    else:
        # Create a task for all environments, and use the first
        # character as alias
        for environment in env.box_environments:
            t = _create_setup_task_for_env(environment)
            shortcut = env.box_environments[environment].get('shortcut')
            aliases = (shortcut,) if shortcut else ()
            fabfile[environment] = task(aliases=aliases)(t)
            fabfile['__all__'] += (environment,)

    # Fabric commands with environment interpolation -------------------------

    def interpolate_with_env(fn):
        """Wrapper which extends a few Fabric API commands to fill in values from
        Fabric's environment dictionary"""
        @wraps(fn)
        def _dec(string, *args, **kwargs):
            return fn(string % env, *args, **kwargs)
        return _dec

    g = globals()
    g['cd'] = interpolate_with_env(cd)
    g['run'] = interpolate_with_env(run)
    g['run_local'] = interpolate_with_env(run_local)
    g['confirm'] = interpolate_with_env(confirm)

    # Git pre-commit hook which always runs "fab check" ----------------------

    def ensure_pre_commit_hook_installed():
        """
        Ensures that ``git commit`` fails if ``fab check`` returns any errors.
        """
        p = Popen('git rev-parse --git-dir'.split(), stdout=PIPE)
        git_dir = p.stdout.read().strip()
        project_dir = dirname(git_dir)

        if not any(exists(join(project_dir, name)) for name in (
                'fabfile.py', 'fabfile')):
            # Does not look like a Django project.
            # Additionally, "fab check" wouldn't work anyway.
            return

        pre_commit_hook_path = join(git_dir, 'hooks', 'pre-commit')
        if not exists(pre_commit_hook_path):
            with open(pre_commit_hook_path, 'w') as hook:
                hook.write('''\
    #!/bin/sh
    fab check
    ''')
            chmod(pre_commit_hook_path, 0o755)

    # Run this each time the fabfile is loaded
    ensure_pre_commit_hook_installed()

    if not exists('tmp'):
        mkdir('tmp')

    from fh_fablib import check, deploy, dev, git, local, server
    fabfile.update({
        'check': check,
        'deploy': deploy,
        'dev': dev,
        'git': git,
        'local': local,
        'server': server,
    })
