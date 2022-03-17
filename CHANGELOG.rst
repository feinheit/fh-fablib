==========
Change log
==========

`Next version`_
~~~~~~~~~~~~~~~

.. _Next version: https://github.com/feinheit/fh-fablib/compare/1.0.20220317...main


`1.0.20220317`_
~~~~~~~~~~~~~~~

.. _1.0.20220317: https://github.com/feinheit/fh-fablib/compare/1.0.20220315...1.0.20220317

- Added yet another missing babel plugin.
- Reversed the default order of ESLint and prettier. ESLint doesn't complain
  about missing prettier formatting, and prettier can cleanup the results of
  ``eslint --fix``.
- Added a ``reset-sq`` task for resetting all PostgreSQL sequences in a
  database.
- Added ``python3.10`` and removed ``python3.7`` and ``python3.6`` from the
  list of Python 3 exexecutables used when initializing projects locally.
- Started initializing submodules in the ``update`` task. Using submodules for
  libraries is still discouraged. We use them so rarely that people forget how
  to do this.


`1.0.20220315`_
~~~~~~~~~~~~~~~

.. _1.0.20220315: https://github.com/feinheit/fh-fablib/compare/1.0.20220311...1.0.20220315

- Added ``verbose: true`` to the ESLint hook configuration so that ESLint
  warnings are shown even if ESLint doesn't find any errors.
- Added a missing babel dependency.
- Added a hook to sort ``.gitignore``.
- Made ESLint automatically apply some fixes.
- Dropped a few legacy check methods; reimplement them in your own fabfile if
  you still need them (or better yet, move to pre-commit).
- Dropped the ``fmt`` task and all utilities. Use pre-commit instead.
- Updated our own pre-commit hooks.


`1.0.20220311`_
~~~~~~~~~~~~~~~

.. _1.0.20220311: https://github.com/feinheit/fh-fablib/compare/1.0.20220211...1.0.20220311

- Changed ``pull-db`` to create a local ``.env`` if it does not exist already.
- Restored the automatic installation of the pre-commit hook.
- Extended ``hook`` with a ``--force`` argument to allow overwriting
  pre-existing files in the project.
- Added ``.editorconfig`` and ``.eslintrc.js`` defaults to ``hook``. Updated
  the ``pre-commit`` configuration.


`1.0.20220211`_
~~~~~~~~~~~~~~~

.. _1.0.20220211: https://github.com/feinheit/fh-fablib/compare/1.0.20220126...1.0.20220211

- Better defaults in the ``.env``: Add ``.localhost`` to the local
  ``ALLOWED_HOSTS`` setting.
- Generate the standard ``SECURE_SSL_*`` settings instead of
  ``CANONICAL_DOMAIN*``.
- Changed force pushes to use ``--force-with-lease``.


`1.0.20220126`_
~~~~~~~~~~~~~~~

.. _1.0.20220126: https://github.com/feinheit/fh-fablib/compare/1.0.20211201...1.0.20220126

- Changed ``systemctl`` invocations to use the ``--now`` switch to immediately
  enable or disable services.
- Added a ``--python3`` argument to ``nine-venv`` which allows overriding the
  Python executable.
- Stop wrapping long lines in pofiles.


`1.0.20211201`_
~~~~~~~~~~~~~~~

- Changed ``fl mm`` to disable ESLint on the generated ``strings.js`` file.
- Added ``*jsx`` files to the gettext extractor.
- Tweaked the pre-commit configuration.


`1.0.20211124`_
~~~~~~~~~~~~~~~

- Changed ``fl check`` to build on ``pre-commit`` instead.


`1.0.20211029`_
~~~~~~~~~~~~~~~

- Added a configuration flag to always use force pushes for select
  environments.


`1.0.20210928`_
~~~~~~~~~~~~~~~

- Added auto-updating of ``fl.require`` statements in projects.


`1.0.20210927`_
~~~~~~~~~~~~~~~

- Added ``pyupgrade`` invocations to ``fl fmt``.
- Changed all ``_fmt_*`` utilities to not stop on errors.


`1.0.20210923`_
~~~~~~~~~~~~~~~

- Fixed the ``djlint`` invocation to actually reformat files.


`1.0.20210922`_
~~~~~~~~~~~~~~~

- Added ``.feinheit.dev`` to the list of ``ALLOWED_HOSTS`` in
  ``nine-db-dotenv``.
- Added ``build`` to the list of ignores.
- Added ``djlint`` invocations to ``fl fmt``.
- Added a ``--clobber`` argument to ``fl local``.


`1.0.20210818`_
~~~~~~~~~~~~~~~

- Fixed the final newline behavior of ``fl mm``'s string extraction.


`1.0.20210816`_
~~~~~~~~~~~~~~~

- Changed the ``pkg-resources``-exclusion in ``fl freeze`` to also match
  ``pkg_resources``.
- Added a ``--language`` flag to ``fl mm`` which is especially useful when
  adding a new language.
- Integrated the gettext string extraction script into ``fl mm``.


`1.0.20210721`_
~~~~~~~~~~~~~~~

- Switch from ``npx`` to ``yarn run``.
- Changed the ``update`` task to not fail when running migrations fails. This
  allows ``fl update pull-db`` to continue.
- Added ``dist`` to the list of folders to skip when running ``makemessages``.


`1.0.20210705`_
~~~~~~~~~~~~~~~

- Added ``--force`` to ``fl deploy`` to make ``git push`` use a force-push.
  This is especially useful to deploy e.g. staging branches which are rewound
  often.
- Added a ``SENTRY_ENVIRONMENT=`` entry to generated ``.env`` files.


`1.0.20210506`_
~~~~~~~~~~~~~~~

- Added a ``pull_media`` task.
- Dropped ``--spec`` arguments from ``pipx run`` invocations. The temporary
  virtual environments will be cached for a maximum of 14 days anyway, so they
  should always be recent enough.


`1.0.20210424`_
~~~~~~~~~~~~~~~

- Added an info message when the fh-fablib version is newer than the required
  version (so that projects' fabfiles are updated more often).


`1.0.20210423`_
~~~~~~~~~~~~~~~

- Changed ``_deploy_django`` (and therefore the default deployment) to use hard
  resets to update the code on the server instead of ff-only merges, but add an
  additional check for uncommitted changes right before resetting as a safety
  measure.


`1.0.20210202`_
~~~~~~~~~~~~~~~

- Added ``config.environment`` holding the name of the active
  environment or ``"default"``.


`1.0.20210127`_
~~~~~~~~~~~~~~~

- Restructured ``fl deploy`` into more building blocks so that
  overriding aspects of the deployment is less work.


`1.0.20210125`_
~~~~~~~~~~~~~~~

- Added ``fl nine-reinit-from``.
- Changed the configuration method for multiple environments.


`1.0.20201226`_
~~~~~~~~~~~~~~~

- Fixed the large files check to skip removed files.
- Changed the large files check to report file sizes in kilobytes.


`1.0.20201223`_
~~~~~~~~~~~~~~~

- Added a check for large files to ``fl check``.


`1.0.20201221`_
~~~~~~~~~~~~~~~

- Added ``fl hook`` to replace the git pre-commit hook.
- Corrected and updated the examples in the README.
- Changed ``fl github`` to terminate  with a better error message when
  the ``origin`` remote is already setup.


`1.0.20201215`_
~~~~~~~~~~~~~~~

- Fixed ``nine-disable`` to backup and drop the database for real.
- Promoted ``_reset_passwords`` to ``reset-pw``.
- Removed the explicit activation of pip's 2020 resolver from pip
  invocations, it is the default now.
- Added ``nine-restart`` to restart the application server.
- Started executing nodejs binaries using ``npx``.
- Avoided pip 20.3.2 because it downloads too many packages.
- Added a ``--fast`` switch to ``deploy`` which skips Webpack.


`1.0.20201110`_
~~~~~~~~~~~~~~~

- Allowed setting the ``environments`` config key to produce nicer error
  messages when forgetting to set an environment with which to interact.


`1.0.20201029`_
~~~~~~~~~~~~~~~

- Started using pip's 2020 resolver when upgrading the virtualenv.
- Started terminating deploys when there are uncommitted changes on
  the server.


`1.0.20201005`_
~~~~~~~~~~~~~~~

- Started sourcing ``.profile`` again when running psql admin commands
  on the server.
- Fixed many problems with obviously untested ``nine-*`` tasks.


`1.0.20201004`_
~~~~~~~~~~~~~~~

- Added ``github`` to create a repo on GitHub using the `GitHub CLI
  <https://cli.github.com/>__` and immediately push the code there.
- Fixed uses of ``input()`` which somehow didn't work like they were
  supposed to at all.


`1.0.20200924`_
~~~~~~~~~~~~~~~

- Renamed the entrypoint from ``fab`` to ``fl``.
- Switched from running ``pip`` directly to the recommended ``python -m
  pip`` everywhere.
- Avoided starting too many processes by executing binaries in
  ``node_modules/.bin`` directly instead of going through ``yarn run``.


`1.0.20200916`_
~~~~~~~~~~~~~~~

- Made ``nine-venv`` recreate the virtualenv from scratch.
- Made ``local`` recreate ``node_modules`` and the virtualenv from
  scratch.


`1.0.20200915`_
~~~~~~~~~~~~~~~

- Fixed ``nine-alias-remove`` to actually remove the second subdomain.
- Added a ``--include-www`` option to ``nine-alias-add`` and
  ``nine-alias-remove``. The ``www.`` subdomain isn't added or removed
  by default anymore.


`1.0.20200907`_
~~~~~~~~~~~~~~~

- Removed the redundant ``--trailing-comma es5`` argument to prettier,
  it is the default.
- Splitted ``_fmt_pipx_cmds`` into ``_fmt_isort`` and ``_fmt_black``.
- Reordered ``fmt`` to run Python tasks first, as ``check`` does.
- Extracted the branch check into its own ``_check_branch`` function.
- Changed ``nine-venv`` to prefer pyenv shims instead of the potentially
  outdated system-provided python3 binary.


`1.0.20200901`_
~~~~~~~~~~~~~~~

- Added our own ``entry_points`` so that the ``--include-deps`` argument
  to ``pipx`` isn't necessary anymore.
- Removed an unnecessary ``# noqa``.
- Stopped running ``flake8`` when formatting code.


`1.0.20200827`_
~~~~~~~~~~~~~~~

- Added the ``--stable`` switch to ``upgrade`` to only install stable
  Python packages, no alpha, beta or rc versions.
- Disabled shortflags to ``dev``.
- Changed the default ``fmt`` implementation to run isort, black and
  flake8 via `pipx <https://pipxproject.github.io/pipx/>`__. It is
  recommended you remove ``isort`` configuration from your project.
- Added default options when running prettier so that prettier
  configuration may be dropped from package.json (ES5 commas, no
  semicolons where not necessary).
- Changed ``check`` to run flake8 using pipx too.
- Inlined the ``dev`` and ``prod`` npm scripts.


`1.0.20200825`_
~~~~~~~~~~~~~~~

- Added a multi-env example to the README.
- Switched to running all commands with ``echo`` and ``pty`` and without
  ``replace_env``.
- Activated rsync stats instead of succeeding silently or filling the
  screen several times with spam when deploying.


`1.0.20200824`_
~~~~~~~~~~~~~~~

- Changed ``nine-db-dotenv`` to terminate when ``.env`` already exists
  on the server.


`1.0.20200822`_
~~~~~~~~~~~~~~~

- Completely changed the structure of this library. Rebuilt the library
  on top of Fabric>2. Dropped old stuff and renamed everything.
- Switched to a date-based versioning scheme, which does NOT follow
  semver.

.. _1.0.20200822: https://github.com/feinheit/fh-fablib/commit/6fd0b89bcd8c0ce
.. _1.0.20200824: https://github.com/feinheit/fh-fablib/compare/1.0.20200822...1.0.20200824
.. _1.0.20200825: https://github.com/feinheit/fh-fablib/compare/1.0.20200824...1.0.20200825
.. _1.0.20200827: https://github.com/feinheit/fh-fablib/compare/1.0.20200825...1.0.20200827
.. _1.0.20200901: https://github.com/feinheit/fh-fablib/compare/1.0.20200827...1.0.20200901
.. _1.0.20200907: https://github.com/feinheit/fh-fablib/compare/1.0.20200901...1.0.20200907
.. _1.0.20200915: https://github.com/feinheit/fh-fablib/compare/1.0.20200907...1.0.20200915
.. _1.0.20200916: https://github.com/feinheit/fh-fablib/compare/1.0.20200915...1.0.20200916
.. _1.0.20200924: https://github.com/feinheit/fh-fablib/compare/1.0.20200915...1.0.20200924
.. _1.0.20201004: https://github.com/feinheit/fh-fablib/compare/1.0.20200924...1.0.20201004
.. _1.0.20201005: https://github.com/feinheit/fh-fablib/compare/1.0.20201004...1.0.20201005
.. _1.0.20201029: https://github.com/feinheit/fh-fablib/compare/1.0.20201005...1.0.20201029
.. _1.0.20201110: https://github.com/feinheit/fh-fablib/compare/1.0.20201029...1.0.20201110
.. _1.0.20201215: https://github.com/feinheit/fh-fablib/compare/1.0.20201110...1.0.20201215
.. _1.0.20201221: https://github.com/feinheit/fh-fablib/compare/1.0.20201215...1.0.20201221
.. _1.0.20201223: https://github.com/feinheit/fh-fablib/compare/1.0.20201221...1.0.20201223
.. _1.0.20201226: https://github.com/feinheit/fh-fablib/compare/1.0.20201223...1.0.20201226
.. _1.0.20210125: https://github.com/feinheit/fh-fablib/compare/1.0.20201226...1.0.20210125
.. _1.0.20210127: https://github.com/feinheit/fh-fablib/compare/1.0.20210125...1.0.20210127
.. _1.0.20210202: https://github.com/feinheit/fh-fablib/compare/1.0.20210127...1.0.20210202
.. _1.0.20210423: https://github.com/feinheit/fh-fablib/compare/1.0.20210202...1.0.20210423
.. _1.0.20210424: https://github.com/feinheit/fh-fablib/compare/1.0.20210423...1.0.20210424
.. _1.0.20210506: https://github.com/feinheit/fh-fablib/compare/1.0.20210424...1.0.20210506
.. _1.0.20210705: https://github.com/feinheit/fh-fablib/compare/1.0.20210506...1.0.20210705
.. _1.0.20210721: https://github.com/feinheit/fh-fablib/compare/1.0.20210705...1.0.20210721
.. _1.0.20210816: https://github.com/feinheit/fh-fablib/compare/1.0.20210721...1.0.20210816
.. _1.0.20210818: https://github.com/feinheit/fh-fablib/compare/1.0.20210816...1.0.20210818
.. _1.0.20210922: https://github.com/feinheit/fh-fablib/compare/1.0.20210818...1.0.20210922
.. _1.0.20210923: https://github.com/feinheit/fh-fablib/compare/1.0.20210822...1.0.20210923
.. _1.0.20210927: https://github.com/feinheit/fh-fablib/compare/1.0.20210923...1.0.20210927
.. _1.0.20210928: https://github.com/feinheit/fh-fablib/compare/1.0.20210927...1.0.20210928
.. _1.0.20211029: https://github.com/feinheit/fh-fablib/compare/1.0.20210928...1.0.20211029
.. _1.0.20211124: https://github.com/feinheit/fh-fablib/compare/1.0.20211029...1.0.20211124
.. _1.0.20211201: https://github.com/feinheit/fh-fablib/compare/1.0.20211124...1.0.20211201
