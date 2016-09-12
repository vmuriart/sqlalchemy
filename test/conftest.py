#!/usr/bin/env python
"""
pytest plugin script.

This script is an extension to py.test which
installs SQLAlchemy's testing plugin into the local environment.

"""
import sys
import os

if not sys.flags.no_user_site:
    # this is needed so that test scenarios like "python setup.py test"
    # work correctly, as well as plain "py.test".  These commands assume
    # that the package in question is locally present, but since we have
    # ./lib/, we need to punch that in.
    # We check no_user_site to honor the use of this flag.
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                    '..', 'lib'))

