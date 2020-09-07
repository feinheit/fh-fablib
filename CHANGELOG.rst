==========
Change log
==========

`Next version`_
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
.. _Next version: https://github.com/feinheit/fh-fablib/compare/1.0.20200901...main
