=========
fh-fablib
=========

Usage (``fabfile.py``)::

    from __future__ import unicode_literals

    from fabric.api import env
    import fh_fablib

    # env.box_environment contains the currently active environment.

    # Default values available in all environments
    env.box_project_name = 'app'
    env.box_domain = 'example.ch'
    env.box_database_local = 'example_ch'
    env.box_staticfiles = '%(box_project_name)s/static/%(box_project_name)s' % env
    env.box_static_src = 'assets'
    env.box_restart = ['sctl restart %(box_domain)s:*']
    env.forward_agent = True

    # Remove this for multi-env support
    env.box_hardwired_environment = 'production'

    # Environment specific values.
    env.box_environments = {
        'production': {
            'shortcut': 'p',
            'domain': 'example.ch',
            'branch': 'master',
            'servers': [
                'user@example.com',
            ],
            'remote': 'production',  # git remote alias for the server.
            'repository': 'example.ch',
            'database': 'example_ch',
        },
        'staging': {
            'shortcut': 's',
            'domain': 'stage.example.ch',
            'branch': 'develop',
            'servers': [
                'user@example.com',
            ],
            'remote': 'staging',
            'repository': 'example.ch',
            'database': 'stage_example_ch',
        },
    }

    fh_fablib.init(globals(), min_version=(0, 1, 7))
