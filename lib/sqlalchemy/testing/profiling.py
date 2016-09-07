# testing/profiling.py
# Copyright (C) 2005-2016 the SQLAlchemy authors and contributors
# <see AUTHORS file>
#
# This module is part of SQLAlchemy and is released under
# the MIT License: http://www.opensource.org/licenses/mit-license.php

"""Profiling support for unit and performance tests.

These are special purpose profiling methods which operate
in a more fine-grained way than nose's profiling plugin.

"""

import os
import sys
from .util import gc_collect
from . import config
import pstats
import collections
import contextlib

try:
    import cProfile
except ImportError:
    cProfile = None
from ..util import jython, pypy, win32, update_wrapper

_current_test = None

# ProfileStatsFile instance, set up in plugin_base
_profile_stats = None


class ProfileStatsFile(object):
    """"Store per-platform/fn profiling results in a file.

    We're still targeting Py2.5, 2.4 on 0.7 with no dependencies,
    so no json lib :(  need to roll something silly

    """

    def __init__(self, filename):
        self.force_write = (
            config.options is not None and
            config.options.force_write_profiles
        )
        self.write = self.force_write or (
            config.options is not None and
            config.options.write_profiles
        )
        self.fname = os.path.abspath(filename)
        self.short_fname = os.path.split(self.fname)[-1]
        self.data = collections.defaultdict(
            lambda: collections.defaultdict(dict))
        self._read()
        if self.write:
            # rewrite for the case where features changed,
            # etc.
            self._write()

    @property
    def platform_key(self):

        dbapi_key = config.db.name + "_" + config.db.driver

        # keep it at 2.7, 3.1, 3.2, etc. for now.
        py_version = '.'.join([str(v) for v in sys.version_info[0:2]])

        platform_tokens = [py_version]
        platform_tokens.append(dbapi_key)
        if jython:
            platform_tokens.append("jython")
        if pypy:
            platform_tokens.append("pypy")
        if win32:
            platform_tokens.append("win")
        platform_tokens.append(
            "nativeunicode"
            if config.db.dialect.convert_unicode
            else "dbapiunicode"
        )
        _has_cext = config.requirements._has_cextensions()
        platform_tokens.append(_has_cext and "cextensions" or "nocextensions")
        return "_".join(platform_tokens)

    def has_stats(self):
        test_key = _current_test
        return (
            test_key in self.data and
            self.platform_key in self.data[test_key]
        )

    def result(self, callcount):
        test_key = _current_test
        per_fn = self.data[test_key]
        per_platform = per_fn[self.platform_key]

        if 'counts' not in per_platform:
            per_platform['counts'] = counts = []
        else:
            counts = per_platform['counts']

        if 'current_count' not in per_platform:
            per_platform['current_count'] = current_count = 0
        else:
            current_count = per_platform['current_count']

        has_count = len(counts) > current_count

        if not has_count:
            counts.append(callcount)
            if self.write:
                self._write()
            result = None
        else:
            result = per_platform['lineno'], counts[current_count]
        per_platform['current_count'] += 1
        return result

    def replace(self, callcount):
        test_key = _current_test
        per_fn = self.data[test_key]
        per_platform = per_fn[self.platform_key]
        counts = per_platform['counts']
        current_count = per_platform['current_count']
        if current_count < len(counts):
            counts[current_count - 1] = callcount
        else:
            counts[-1] = callcount
        if self.write:
            self._write()

    def _header(self):
        return (
                   "# %s\n"
                   "# This file is written out on a per-environment basis.\n"
                   "# For each test in aaa_profiling, the corresponding "
                   "function and \n"
                   "# environment is located within this file.  "
                   "If it doesn't exist,\n"
                   "# the test is skipped.\n"
                   "# If a callcount does exist, it is compared "
                   "to what we received. \n"
                   "# assertions are raised if the counts do not match.\n"
                   "# \n"
                   "# To add a new callcount test, apply the function_call_count \n"
                   "# decorator and re-run the tests using the --write-profiles \n"
                   "# option - this file will be rewritten including the new count.\n"
                   "# \n"
               ) % (self.fname)

    def _read(self):
        try:
            profile_f = open(self.fname)
        except IOError:
            return
        for lineno, line in enumerate(profile_f):
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            test_key, platform_key, counts = line.split()
            per_fn = self.data[test_key]
            per_platform = per_fn[platform_key]
            c = [int(count) for count in counts.split(",")]
            per_platform['counts'] = c
            per_platform['lineno'] = lineno + 1
            per_platform['current_count'] = 0
        profile_f.close()

    def _write(self):
        print(("Writing profile file {0!s}".format(self.fname)))
        profile_f = open(self.fname, "w")
        profile_f.write(self._header())
        for test_key in sorted(self.data):

            per_fn = self.data[test_key]
            profile_f.write("\n# TEST: {0!s}\n\n".format(test_key))
            for platform_key in sorted(per_fn):
                per_platform = per_fn[platform_key]
                c = ",".join(str(count) for count in per_platform['counts'])
                profile_f.write(
                    "{0!s} {1!s} {2!s}\n".format(test_key, platform_key, c))
        profile_f.close()


def function_call_count(variance=0.05):
    """Assert a target for a test case's function call count.

    The main purpose of this assertion is to detect changes in
    callcounts for various functions - the actual number is not as important.
    Callcounts are stored in a file keyed to Python version and OS platform
    information.  This file is generated automatically for new tests,
    and versioned so that unexpected changes in callcounts will be detected.

    """

    def decorate(fn):
        def wrap(*args, **kw):
            with count_functions(variance=variance):
                return fn(*args, **kw)

        return update_wrapper(wrap, fn)

    return decorate


@contextlib.contextmanager
def count_functions(variance=0.05):
    if cProfile is None:
        raise SkipTest("cProfile is not installed")

    if not _profile_stats.has_stats() and not _profile_stats.write:
        config.skip_test(
            "No profiling stats available on this "
            "platform for this function.  Run tests with "
            "--write-profiles to add statistics to %s for "
            "this platform." % _profile_stats.short_fname)

    gc_collect()

    pr = cProfile.Profile()
    pr.enable()
    # began = time.time()
    yield
    # ended = time.time()
    pr.disable()

    # s = compat.StringIO()
    stats = pstats.Stats(pr, stream=sys.stdout)

    # timespent = ended - began
    callcount = stats.total_calls

    expected = _profile_stats.result(callcount)

    if expected is None:
        expected_count = None
    else:
        line_no, expected_count = expected

    print(("Pstats calls: {0:d} Expected {1!s}".format(
        callcount,
        expected_count
    )
    ))
    stats.sort_stats("cumulative")
    stats.print_stats()

    if expected_count:
        deviance = int(callcount * variance)
        failed = abs(callcount - expected_count) > deviance

        if failed or _profile_stats.force_write:
            if _profile_stats.write:
                _profile_stats.replace(callcount)
            else:
                raise AssertionError(
                    "Adjusted function call count %s not within %s%% "
                    "of expected %s, platform %s. Rerun with "
                    "--write-profiles to "
                    "regenerate this callcount."
                    % (
                        callcount, (variance * 100),
                        expected_count, _profile_stats.platform_key))
