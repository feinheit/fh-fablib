from __future__ import unicode_literals

import getpass

from fabric.api import env, hide, hosts, prompt, settings, task
from fabric.colors import red
from fabric.contrib.console import confirm
from fabric.utils import puts

from fh_fablib import run_local, require_env, step
from fh_fablib.utils import default_env


@task
@hosts("")
def init_bitbucket():
    username = default_env("BITBUCKET_USERNAME")
    password = default_env("BITBUCKET_PASSWORD")  # Should probably not be used
    organization = default_env("BITBUCKET_ORGANIZATION")

    if not username or not organization:
        puts(
            "Consider adding default values for BITBUCKET_USERNAME"
            " and BITBUCKET_ORGANIZATION to ~/.box.env"
        )

    username = prompt("Username", default=username)
    if not password:
        password = getpass.getpass("Password ")
    organization = prompt("Organization", default=organization)
    repository = prompt("Repository", default=env.box_domain)

    if not confirm(
        "Initialize repository at https://bitbucket.org/%s/%s?"
        % (organization, repository)
    ):

        puts(red("Bitbucket repository creation aborted."))
        return 1

    if username and password and organization and repository:
        env.box_auth = '%s:"%s"' % (username, password)
        env.box_repo = "%s/%s" % (organization, repository)

        with hide("running"):
            run_local(
                "curl"
                " -X POST -v -u %(box_auth)s"
                ' -H "content-type: application/json"'
                " https://api.bitbucket.org/2.0/repositories/%(box_repo)s"
                ' -d \'{"scm": "git", "is_private": true,'
                ' "forking_policy": "no_public_forks"}\''
            )

        with hide("everything"):
            with settings(warn_only=True):
                run_local("git remote rm origin")

        run_local("git remote add origin git@bitbucket.org:%(box_repo)s.git")
        run_local("git push -u origin master")


@task
@require_env
def add_remote():
    """ Add a server repository as git remote  """
    env.box_idx = (
        "" if len(env.hosts) < 2 else "-%d" % (env.hosts.index(env.host_string) + 1)
    )

    with settings(warn_only=True):
        run_local(
            "git remote add -f %(box_remote)s%(box_idx)s"
            " %(host_string)s:%(box_domain)s/"
        )


@task
@require_env
def fetch_remote():
    step("Updating git remote...")
    env.box_idx = (
        "" if len(env.hosts) < 2 else "-%d" % (env.hosts.index(env.host_string) + 1)
    )

    with settings(warn_only=True):
        run_local("git fetch %(box_remote)s%(box_idx)s")
