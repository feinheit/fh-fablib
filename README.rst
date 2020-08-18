=========
fh-fablib
=========

Usage
=====

1. Install `pipx <https://pipxproject.github.io/pipx/>`__
2. ``pipx install --editable git+ssh://git@github.com/feinheit/fh-fablib.git@main#egg=fh_fablib --include-deps``
3. Add a ``fabfile.py`` to your project. A minimal example follows:
   .. code-block:: python

    import fh_fablib as fl
    from fh_fablib import Collection, Path, env

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

    ns = Collection(*fl.GENERAL, *fl.NINE)

4. Run ``fab --list`` to get a list of commands.


Adding or overriding bundled tasks
==================================

For the sake of an example, suppose that frontend assets should be built
some other way. A custom ``deploy`` task follows:

.. code-block:: python

    # ... continuing the fabfile above

    from fh_fablib import Connection, env, task

    @task
    def deploy(ctx):
        """Deploy once 🔥"""
        fl.check(ctx)
        ctx.run(f"git push origin {env.branch}")
        ctx.run("node frontend.js build")

        with Connection(env.host, forward_agent=True) as conn:
            fl._srv_deploy(conn, rsync_static=True)
            conn.run("systemctl --user restart gunicorn@example.com.service")

        fl.fetch(ctx)

    ns.add_task(deploy)
