# -*- coding: utf-8 -*-
#                     The LLVM Compiler Infrastructure
#
# This file is distributed under the University of Illinois Open Source
# License. See LICENSE.TXT for details.

""" This module is responsible for the Clang executable.

Since Clang command line interface is so reach, but this project is using only
a subset of that, it makes sense to create a function specific wrapper. """

import subprocess
import logging
import re
import shlex
import itertools
import functools
from analyzer.decorators import trace


@trace
def get_version(cmd):
    """ Returns the compiler version as string. """
    lines = subprocess.check_output([cmd, '-v'], stderr=subprocess.STDOUT)
    return lines.decode('ascii').splitlines()[0]


@trace
def get_arguments(cwd, command):
    """ Capture Clang invocation.

    Clang can be executed directly (when you just ask specific action to
    execute) or indirect way (whey you first ask Clang to print the command
    to run for that compilation, and then execute the given command).

    This method receives the full command line for direct compilation. And
    it generates the command for indirect compilation. """

    def lastline(stream):
        last = None
        for line in stream:
            last = line
        if last is None:
            raise Exception("output not found")
        return last

    def strip_quotes(quoted):
        match = re.match(r'^\"([^\"]*)\"$', quoted)
        return match.group(1) if match else quoted

    cmd = command[:]
    cmd.insert(1, '-###')
    logging.debug('exec command in {0}: {1}'.format(cwd, ' '.join(cmd)))
    child = subprocess.Popen(cmd,
                             cwd=cwd,
                             universal_newlines=True,
                             stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT)
    line = lastline(child.stdout)
    child.stdout.close()
    child.wait()
    if 0 == child.returncode:
        if re.match(r'^clang: error:', line):
            raise Exception(line)
        return [strip_quotes(x) for x in shlex.split(line)]
    else:
        raise Exception(line)


@trace
def _get_active_checkers(clang, plugins):
    """ To get the default plugins we execute Clang to print how this
    compilation would be called. For input file we specify stdin. And
    pass only language information. """

    def checkers(language, load):
        """ Returns a list of active checkers for the given language. """
        cmd = [clang, '--analyze'] + load + ['-x', language, '-']
        pattern = re.compile(r'^-analyzer-checker=(.*)$')
        return (pattern.match(arg).group(1)
                for arg in get_arguments('.', cmd) if pattern.match(arg))

    load = functools.reduce(
        lambda acc, x: acc + ['-Xclang', '-load', '-Xclang', x],
        plugins,
        [])

    return set(
        itertools.chain.from_iterable(
            checkers(language, load)
            for language
            in ['c', 'c++', 'objective-c', 'objective-c++']))


@trace
def get_checkers(clang, plugins):
    """ Get all the available checkers from default and from the plugins.

    clang -- the compiler we are using
    plugins -- list of plugins which was requested by the user

    This method returns a dictionary of all available checkers and status.

    {<plugin name>: (<plugin description>, <is active by default>)} """

    plugins = plugins if plugins else []

    def parse_checkers(stream):
        """ Parse clang -analyzer-checker-help output.

        Below the line 'CHECKERS:' are there the name description pairs.
        Many of them are in one line, but some long named plugins has the
        name and the description in separate lines.

        The plugin name is always prefixed with two space character. The
        name contains no whitespaces. Then followed by newline (if it's
        too long) or other space characters comes the description of the
        plugin. The description ends with a newline character.
        """
        # find checkers header
        for line in stream:
            if re.match(r'^CHECKERS:', line):
                break
        # find entries
        state = None
        for line in stream:
            if state and not re.match(r'^\s\s\S', line):
                yield (state, line.strip())
                state = None
            elif re.match(r'^\s\s\S+$', line.rstrip()):
                state = line.strip()
            else:
                pattern = re.compile(r'^\s\s(?P<key>\S*)\s*(?P<value>.*)')
                match = pattern.match(line.rstrip())
                if match:
                    current = match.groupdict()
                    yield (current['key'], current['value'])

    def is_active(actives, entry):
        """ Returns true if plugin name is matching the active plugin names.

        actives -- set of active plugin names (or prefixes).
        entry -- the current plugin name to judge.

        The active plugin names are specific plugin names or prefix of some
        names. One example for prefix, when it say 'unix' and it shall match
        on 'unix.API', 'unix.Malloc' and 'unix.MallocSizeof'. """
        return any(re.match(r'^' + a + r'(\.|$)', entry) for a in actives)

    actives = _get_active_checkers(clang, plugins)

    load = functools.reduce(lambda acc, x: acc + ['-load', x], plugins, [])
    cmd = [clang, '-cc1'] + load + ['-analyzer-checker-help']

    logging.debug('exec command: {0}'.format(' '.join(cmd)))
    child = subprocess.Popen(cmd,
                             universal_newlines=True,
                             stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT)
    checkers = {k: (v, is_active(actives, k))
                for k, v
                in parse_checkers(child.stdout)}
    child.stdout.close()
    child.wait()
    if 0 == child.returncode and len(checkers):
        return checkers
    else:
        raise Exception('Could not query Clang for available checkers.')
