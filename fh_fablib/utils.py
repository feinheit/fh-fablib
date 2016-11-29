from __future__ import unicode_literals

import os
import random

import speckenv


def get_random_string(length, chars=None):
    """Returns a random string; mostly used to generate passwords and
    the contents of SECRET_KEY"""
    rand = random.SystemRandom()
    if chars is None:
        chars = 'abcdefghijklmnopqrstuvwxyz0123456789!@#$%^&*(-_=+)'
    return ''.join(rand.choice(chars) for i in range(length))


def default_env(*args, **kwargs):
    if not getattr(default_env, '_loaded', False):
        path = os.path.join(
            os.path.expanduser('~'),
            '.box.env',
        )
        if os.path.isfile(path):
            speckenv.read_speckenv(path)

        default_env._loaded = True

    return speckenv.env(*args, **kwargs)
