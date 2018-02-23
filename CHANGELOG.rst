==========
Change log
==========

`Next version`_
~~~~~~~~~~~~~~~

- Added a new task ``dev.optimize`` which optimizes svg, jpg and
  png files using svgo and imagemagick (convert).
- Replaced ``local.empty_to_password`` with ``local.reset_passwords``,
  which clobbers all passwords and does not require help from a
  management command inside the project.
- Added ``git.add_remote`` to ``local.setup_with_production_data``.
- Removed support for django-admin-sso and creating SSO users; it did
  not work with django-authlib anymore.
- Removed ``FORCE_DOMAIN`` from the servers' ``.env`` file.
- Changed ``local.create_and_migrate_database`` to the shorter
  ``local.create_database``.
- Added ``server.ssl``, ``server.add_alias`` and
  ``server.remove_alias``.
- Added the possibility to override the systemd unit template, e.g. if
  using ``daphne`` instead of ``gunicorn`` by setting
  ``env.box_unit_template``.
- Shortened ``makemessages`` and ``compilemessages`` to ``mm`` and
  ``cm``.
- Fix the ``server.add_alias`` and the ``server.remove_alias`` command.
  The alias was mistakenly used as the name of the virtual host.


0.6 (2017-12-19)
~~~~~~~~~~~~~~~~

- Reversed the order of ``local.update`` and ``local.empty_to_password``
  (migrations may have to be applied first).
- Runserver always binds to ``0.0.0.0`` (as webpack-dev-server already
  does) to make it easier to develop inside vagrant boxes with forwarded
  ports.
- Made ``ALLOWED_HOSTS`` on the server not contain redundant entries.
- ``server.dump_db`` and a few other commands now use the connection
  string from the remote ``.env``
- Added a call to ``./manage.py check --deploy`` on the server to detect
  missing settings before attempting a restart.
- Added support for supervising processes using user systemd instead of
  supervisord.
- Made the arguments (currently ``min_version`` and ``systemd``) to
  ``fh_fablib.init()`` mandatory.
- Added a check whether our branch is up to date before the expensive
  tests and asset compiling steps.


0.5 (2017-08-25)
~~~~~~~~~~~~~~~~

- Made it possible to override ``check``, ``test`` and ``prettify``
  commands used.
- Added a ``prettier`` alias for ``prettify``.
- Removed ``@require_env`` where it was unnecessary.


0.4 (2017-06-23)
~~~~~~~~~~~~~~~~

- ``pull_database`` now uses the connection string from the remote
  ``.env`` instead of assuming an available admin user.
- Run ``prettier`` to format JavaScript and SCSS code in ``fab check``.
- Dropped all pre-webpack2 compatibility code.


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
