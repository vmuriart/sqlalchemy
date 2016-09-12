# databases/__init__.py
# Copyright (C) 2005-2016 the SQLAlchemy authors and contributors
# <see AUTHORS file>
#
# This module is part of SQLAlchemy and is released under
# the MIT License: http://www.opensource.org/licenses/mit-license.php

"""Include imports from the sqlalchemy.dialects package for backwards
compatibility with pre 0.6 versions.

"""
from ..dialects.sqlite import base as sqlite
from ..dialects.oracle import base as oracle

__all__ = (
    'sqlite',
    'oracle',
)
