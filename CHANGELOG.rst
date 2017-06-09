==========
Change log
==========

`Next version`_
~~~~~~~~~~~~~~~

- ``pull_database`` now uses the connection string from the remote
  ``.env`` instead of assuming an available admin user.


0.3 (2017-05-16)
~~~~~~~~~~~~~~~~

- Dropped ``pull_mediafiles`` from ``setup_with_production_data``.
- Only show Python warnings once.
- Optionally allow cleaning the static folder on deployment.
- Run a bare ``manage.py test`` again now that ``fabfile`` is a file,
  not a module again.
- Fixed paths for DB dumps (relative to CWD, not relative to
  ``fh-fablib``)
- ``update_requirements``: Always fully regenerate the virtualenv
- Dropped the migration step from ``local.pull``

0.2 (2017-02-03)
~~~~~~~~~~~~~~~~

- Dropped support for Python 2-based projects.
- ``server.copy_data_from``: Do not fail when files exist already in the
  media folder.
- Added support for the new webpack2-based project structure.
- Added support for yarn besides npm.
- Added support for specifying the minimum required version of fh-fablib.
- Added support for saying ``fab dev:net`` for an easy way to start a
  development server on an IP reachable from the local network.

0.1 (2016-11-29)
~~~~~~~~~~~~~~~~

- Initial release.
