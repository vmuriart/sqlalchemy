# sqlite/__init__.py
# Copyright (C) 2005-2016 the SQLAlchemy authors and contributors
# <see AUTHORS file>
#
# This module is part of SQLAlchemy and is released under
# the MIT License: http://www.opensource.org/licenses/mit-license.php

from sqlalchemy.dialects.sqlite import base, pysqlite

# default dialect
base.dialect = pysqlite.dialect
