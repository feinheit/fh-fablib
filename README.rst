=========
fh-fablib
=========

Usage
=====

1. Install `pipx <https://pipxproject.github.io/pipx/>`__
2. Install fh-fablib

   a. ``pipx install fh_fablib`` if you're happy with the packaged version
   b. ``pipx install ~/Projects/fh-fablib`` if you have a local git checkout
      you want to install from

3. Add a ``fabfile.py`` to your project. A minimal example follows:

   .. code-block:: python

       import fh_fablib as fl

       fl.require("1.0.20221102")
       fl.config.update(host="www-data@feinheit06.nine.ch")

       environments = [
           fl.environment(
               "production",
               {
                   "domain": "example.com",
                   "branch": "main",
                   "remote": "production",
               },
               aliases=["p"],
           ),
       ]

       ns = fl.Collection(*fl.GENERAL, *fl.NINE, *environments)

4. Run ``fl hook`` to provide a default `pre-commit
   <https://pre-commit.com/>`__ configuration (or ``fl hook --force`` to
   override the dotfiles).

5. Run ``fl --list`` to get a list of commands.


Configuration values
====================

- ``app = "app"``: Name of primary Django app containing settings, assets etc.
- ``base``: ``pathlib.Path`` object pointing to the base dir of the project.
- ``branch``: Branch containing code to be deployed.
- ``domain``: Primary domain of website. The database name and cache key
  prefix are derived from this value.
- ``environments``: A dictionary of environments, see below.
- ``environment``: The name of the active environment or ``"default"``.
- ``force``: Always force-push when deploying.
- ``host``: SSH connection string (``username@server``)
- ``remote``: git remote name for the server. Only used for the
  ``fetch`` task.


Adding or overriding bundled tasks
==================================

For the sake of an example, suppose that additional processes should be
restarted after deployment. A custom ``deploy`` task follows:

.. code-block:: python

    # ... continuing the fabfile above

    @fl.task
    def deploy(ctx):
        """Deploy once 🔥"""
        fl.deploy(ctx)  # Reuse
        with fl.Connection(fl.config.host) as conn:
            fl.run(conn, "systemctl --user restart other.service")

    ns.add_task(deploy)

.. note::

   Instead of making existing tasks more flexible or configurable it's
   preferable to contribute better building blocks resp. to improve
   existing buildings blocks to make it easier to build customized tasks
   inside projects.


Multiple environments
=====================

If you need multiple environments, add environment tasks as follows:

.. code-block:: python

    import fh_fablib as fl

    fl.require("1.0.20221102")
    fl.config.update(host="www-data@feinheit06.nine.ch")

    environments = [
        fl.environment(
            "production",
            {
                "domain": "example.com",
                "branch": "main",
                "remote": "production",
            },
            aliases=["p"],
        ),
        fl.environment(
            "next",
            {
                "domain": "next.example.com",
                "branch": "next",
                "remote": "next",
            },
            aliases=["n"],
        ),
    ]

    ns = fl.Collection(*fl.GENERAL, *fl.NINE, *environments)


Now, ``fl production pull-db``, ``fl next deploy`` and friends should
work as expected.


Available tasks
===============

``fh_fablib.GENERAL``
~~~~~~~~~~~~~~~~~~~~~

- ``check``: Check the coding style
- ``cm``: Compile the translation catalogs
- ``deploy``: Deploy once 🔥
- ``dev``: Run the development server for the frontend and backend
- ``fetch``: Ensure a remote exists for the server and fetch
- ``freeze``: Freeze the virtualenv's state
- ``github``: Create a repository on GitHub and push the code
- ``hook``: Install the pre-commit hook
- ``local``: Local environment setup
- ``mm``: Update the translation catalogs
- ``pull-db``: Pull a local copy of the remote DB and reset all passwords
- ``pull-media``: Rsync a folder from the remote to the local environment
- ``reset-pw``: Set all user passwords to ``"password"``
- ``reset-sq``: Reset all PostgreSQL sequences
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
- ``nine-reinit-from``: Reinitialize an environment from a different environment
- ``nine-restart``: Restart the application server
- ``nine-ssl``: Activate SSL
- ``nine-unit``: Start and enable a gunicorn@ unit
- ``nine-venv``: Create a venv and install packages from requirements.txt
- ``nine-vhost``: Create a virtual host using nine-manage-vhosts


Building blocks
===============

The following functions may be used to build your own tasks. They cannot
be executed directly from the command line.

Running commands
~~~~~~~~~~~~~~~~~

- ``run(c, ...)``: Wrapper around ``Context.run`` or ``Connection.run``
  which always sets a few useful arguments (``echo=True``, ``pty= True``
  and ``replace_env=False`` at the time of writing)


Checks
~~~~~~

- ``_check_branch(ctx)``: Terminates if checked out branch does not
  match configuration.
- ``_check_no_uncommitted_changes(ctx)``: Terminates if there are
  uncommitted changes on the server.


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
- ``_dbname_from_dsn(dsn)``: Extract the database name from a DSN.
- ``_dbname_from_domain(domain)``: Mangle the domain to produce a string
  suitable as a database name, database user and cache key prefix.
- ``_concurrently(ctx, jobs)``: Run a list of shell commands
  concurrently and wait for all of them to terminate (or Ctrl-C).
- ``_random_string(length, chars=None)``: Return a random string of
  length, suitable for generating secret keys etc.
- ``require(version)``: Terminate if fh_fablib is older.
- ``terminate(msg)``: Terminate processing with an error message.


Deployment
~~~~~~~~~~

- ``_deploy_django``: Update the Git checkout, update the virtualenv.
- ``_deploy_staticfiles``: Collect staticfiles.
- ``_rsync_static``: rsync the local ``static/`` folder to the remote,
  optionally deleting everything which doesn't exist locally.
- ``_nine_restart``: Restart the systemd control unit.
