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


Available tasks
===============

``fh_fablib.GENERAL``
~~~~~~~~~~~~~~~~~~~~~

- ``bitbucket``: Create a repository on Bitbucket and push the code
- ``check``: Check the coding style
- ``cm``: Compile the translation catalogs
- ``deploy``: Deploy once 🔥
- ``dev``: Run the development server for the frontend and backend
- ``fetch``: Add and fetch refs from the server
- ``fmt``: Format the code
- ``freeze``: Freeze the virtualenv's state
- ``local``: Local environment setup
- ``mm``: Update the translation catalogs
- ``pull-db``: Pull a local copy of the remote DB and reset all passwords
- ``update``: Update virtualenv and node_modules to match the lockfiles
- ``upgrade``: Re-create the virtualenv with newest versions of all libraries


``fh_fablib.NINE``
~~~~~~~~~~~~~~~~~~

- ``nine``: Run all nine🌟 setup tasks in order
- ``nine-alias-add``: Add aliasses to a nine-manage-vhost virtual host
- ``nine-alias-remove``: Remove aliasses from a nine-manage-vhost virtual host
- ``nine-checkout``: Checkout the repository on the server
- ``nine-db-dotenv``: Create a database and initialize the .env
- ``nine-disable``: Disable a virtual host, dump and remove the DB and stop the gunicorn@ unit
- ``nine-ssl``: Activate SSL
- ``nine-unit``: Start and enable a gunicorn@ unit
- ``nine-venv``: Create a venv and install packages from requirements.txt
- ``nine-vhost``: Create a virtual host using nine-manage-vhosts
