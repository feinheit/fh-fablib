==========
Change log
==========

`Next version`_
~~~~~~~~~~~~~~~

- Added the ``--stable`` switch to ``upgrade`` to only install stable
  Python packages, no alpha, beta or rc versions.
- Disabled shortflags to ``dev``.


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

.. _Next version: https://github.com/feinheit/fh-fablib/compare/1.0.20200825...main
.. _1.0.20200825: https://github.com/feinheit/fh-fablib/compare/1.0.20200824...1.0.20200825
.. _1.0.20200824: https://github.com/feinheit/fh-fablib/compare/1.0.20200822...1.0.20200824
.. _1.0.20200822: https://github.com/feinheit/fh-fablib/commit/6fd0b89bcd8c0ce
