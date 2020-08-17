=========
fh-fablib
=========

Usage
=====

``fabfile.py``:

.. code-block:: python

    import fh_fablib as fl
    from fh_fablib import Collection, Connection, Path, env, task


    env.update(
        {
            "base": Path(__file__).parent,
            "host": "www-data@feinheit06.nine.ch",
            "domain": "example.com",
            "database": "example_com",
            "branch": "master",
        }
    )


    @task
    def deploy(c):
        check(c)
        c.run(f"git push origin {env.branch}")
        c.run("yarn run prod")

        with Connection(env.host, forward_agent=True) as c:
            fl._srv_deploy(c, branch=env.branch, domain=env.domain, rsync_static=True)
            c.run("systemctl --user restart gunicorn@example.com.service")


    @task
    def check(c):
        fl._check_flake8(c)
        fl._check_django(c)
        fl._check_prettier(c)
        fl._check_eslint(c)


    @task
    def fmt(c):
        fl._fmt_prettier(c)
        fl._fmt_tox_style(c)


    ns = Collection(
        fl.cm,
        fl.dev,
        fl.mm,
        fl.upgrade,
        fl.freeze,
        fl.update,
        fl.pull_db,
        fl.local,
        # Nine
        fl.nine_vhost,
        fl.nine_unit,
        fl.nine_db_dotenv,
        fl.nine_ssl,
        fl.nine_disable,
        # Custom
        check,
        deploy,
        fmt,
    )


    # task(init_bitbucket)
    # task(nine_alias)


Installation
============

1. Install `pipx <https://pipxproject.github.io/pipx/>`__
2. ``pipx install --editable git+ssh://git@github.com/feinheit/fh-fablib.git@main#egg=fh_fablib --include-deps``
3. Run ``fab --list`` to get a list of commands.
