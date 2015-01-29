# -*- coding: utf-8 -*-
#                     The LLVM Compiler Infrastructure
#
# This file is distributed under the University of Illinois Open Source
# License. See LICENSE.TXT for details.

from . import test_command
from . import test_clang
from . import test_runner
from . import test_report
from . import test_decorators
from . import test_beye
from . import test_bear


def load_tests(loader, suite, pattern):
    suite.addTests(loader.loadTestsFromModule(test_command))
    suite.addTests(loader.loadTestsFromModule(test_clang))
    suite.addTests(loader.loadTestsFromModule(test_runner))
    suite.addTests(loader.loadTestsFromModule(test_report))
    suite.addTests(loader.loadTestsFromModule(test_decorators))
    suite.addTests(loader.loadTestsFromModule(test_beye))
    suite.addTests(loader.loadTestsFromModule(test_bear))
    return suite
