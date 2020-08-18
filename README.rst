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
       from fh_fablib import Collection, Path, config

       config.update(
           base=Path(__file__).parent,
           host="www-data@feinheit06.nine.ch",
           domain="example.com",
           branch="main",
           remote="production",
       )

       ns = Collection(*fl.GENERAL, *fl.NINE)

4. Run ``fab --list`` to get a list of commands.

Loading the ``fh_fablib`` module automatically creates
``.git/hooks/pre-commit`` which runs ``fab check`` before each commit.


Configuration values
====================

- ``app = "app"``: Name of primary Django app containing settings, assets etc.
- ``base``: ``pathlib.Path`` object pointing to the base dir of the project.
- ``branch``: Branch containing code to be deployed.
- ``domain``: Primary domain of website. The database name and cache key
  prefix are derived from this value.
- ``host``: SSH connection string (``username@server``)
- ``remote``: git remote name for the server. Only used for the
  ``fetch`` task.


Adding or overriding bundled tasks
==================================

For the sake of an example, suppose that frontend assets should be built
some other way. A custom ``deploy`` task follows:

.. code-block:: python

    # ... continuing the fabfile above

    from fh_fablib import Connection, config, task

    @task
    def deploy(ctx):
        """Deploy once 🔥"""
        fl.check(ctx)
        ctx.run(f"git push origin {config.branch}")
        ctx.run("node frontend.js build")

        with Connection(config.host) as conn:
            fl._srv_deploy(conn)

        fl.fetch(ctx)

    ns.add_task(deploy)

.. note::

   Instead of making existing tasks more flexible or configurable it's
   preferable to contribute better building blocks resp. to improve
   existing buildings blocks to make it easier to build customized tasks
   inside projects. E.g. if you want to ``fmt`` additional paths it's
   better to build your own ``fmt`` task and not add configuration
   variables to the ``config`` dictionary.


Available tasks
===============

``fh_fablib.GENERAL``
~~~~~~~~~~~~~~~~~~~~~

- ``bitbucket``: Create a repository on Bitbucket and push the code
- ``check``: Check the coding style
- ``cm``: Compile the translation catalogs
- ``deploy``: Deploy once 🔥
- ``dev``: Run the development server for the frontend and backend
- ``fetch``: Ensure a remote exists for the server and fetch
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
- ``nine-db-dotenv``: Create a database and initialize the .env.
  Currently assumes that the shell user has superuser rights (either
  through ``PGUSER`` and ``PGPASSWORD`` environment variables or through
  peer authentication)
- ``nine-disable``: Disable a virtual host, dump and remove the DB and
  stop the gunicorn@ unit
- ``nine-ssl``: Activate SSL
- ``nine-unit``: Start and enable a gunicorn@ unit
- ``nine-venv``: Create a venv and install packages from requirements.txt
- ``nine-vhost``: Create a virtual host using nine-manage-vhosts


Building blocks
===============

The following functions may be used to build your own tasks. They cannot
be executed directly from the command line.

Checks
~~~~~~

- ``_check_flake8(ctx)``: Run ``venv/bin/flake8``
- ``_check_django(ctx)``: Run Django's checks
- ``_check_prettier(ctx)``: Check whether the frontend code conforms to
  prettier's formatting
- ``_check_eslint(ctx)``: Run ESLint


Formatters
~~~~~~~~~~

- ``_fmt_prettier(ctx)``: Run ``prettier``
- ``_fmt_tox_style(ctx)``: Run ``tox -e style``


Helpers
~~~~~~~

- ``_local_env(path=".env")``: ``speckenv.env`` for a local env file
- ``_srv_env(conn, path)``: ``speckenv.env`` for a remote env file
- ``_python3()``: Return the path of a Python 3 executable. Prefers
  newer Python versions.
- ``_local_dotenv_if_not_exists()``: Ensure a local ``.env`` with a few
  default values exists. Does nothing if ``.env`` exists already.
- ``_local_dbname()``: Ensure a local ``.env`` exists and return the
  database name.
