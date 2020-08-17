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
            "branch": "main",
            "remote": "production",
        }
    )


    @task
    def deploy(ctx):
        """Deploy once 🔥"""
        fl.check(ctx)
        ctx.run(f"git push origin {env.branch}")
        ctx.run("yarn run prod")

        with Connection(env.host, forward_agent=True) as conn:
            fl._srv_deploy(conn, rsync_static=True)
            conn.run("systemctl --user restart gunicorn@example.com.service")

        fl.fetch(ctx)


    ns = Collection(*fl.GENERAL, *fl.NINE)
    ns.add_task(deploy)


Installation
============

1. Install `pipx <https://pipxproject.github.io/pipx/>`__
2. ``pipx install --editable git+ssh://git@github.com/feinheit/fh-fablib.git@main#egg=fh_fablib --include-deps``
3. Run ``fab --list`` to get a list of commands.
