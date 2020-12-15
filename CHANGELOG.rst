==========
Change log
==========

`Next version`_
~~~~~~~~~~~~~~~


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
.. _Next version: https://github.com/feinheit/fh-fablib/compare/1.0.20201215...main
