from __future__ import unicode_literals

import os
import random
import shutil
import tempfile

from fabric.api import env, get
import speckenv


def get_random_string(length, chars=None):
    """Returns a random string; mostly used to generate passwords and
    the contents of SECRET_KEY"""
    rand = random.SystemRandom()
    if chars is None:
        chars = "abcdefghijklmnopqrstuvwxyz0123456789!@#$%^&*(-_=+)"
    return "".join(rand.choice(chars) for i in range(length))


def default_env(*args, **kwargs):
    if not getattr(default_env, "_loaded", False):
        path = os.path.join(os.path.expanduser("~"), ".box.env")
        if os.path.isfile(path):
            speckenv.read_speckenv(path)

        default_env._loaded = True

    return speckenv.env(*args, **kwargs)


class TemporaryDirectory(object):
    """
    Context manager for tempfile.mkdtemp().
    This class is available in python +v3.2.
    """

    def __enter__(self):
        self.dir_name = tempfile.mkdtemp()
        return self.dir_name

    def __exit__(self, exc_type, exc_value, traceback):
        shutil.rmtree(self.dir_name)


REMOTE_ENV = None


def remote_env(*args, **kwargs):
    global REMOTE_ENV

    if REMOTE_ENV is None:
        REMOTE_ENV = {}
        with TemporaryDirectory() as d:
            get("%(box_domain)s/.env" % env, d)
            speckenv.read_speckenv(os.path.join(d, ".env"), mapping=REMOTE_ENV)

    kwargs["mapping"] = REMOTE_ENV
    return speckenv.env(*args, **kwargs)
