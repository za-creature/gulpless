# coding=utf-8
from __future__ import absolute_import, unicode_literals, division

import pathtools.patterns
import termcolor
import logging
import shutil
import time
import re
import os


class TimedSet(set):
    __slots__ = ["updated"]

    def __init__(self, updated):
        self.updated = updated
        super(TimedSet, self).__init__()


class Handler(object):
    def __init__(self, patterns, ignore_patterns=None, suffixes=[""]):
        """Creates a new handler. `patterns` and `ignore_patterns` are lists of
        glob patterns that determine what files this handler operates on.
        `suffixes` is a list of extensions that will be added to a input file
        to produce output files (the files will be produced in the output
        folder, but will respect the input folder structure)."""
        super(Handler, self).__init__()

        self.patterns = [os.path.normcase(pattern) for pattern in patterns]

        self.ignore_patterns = None
        if ignore_patterns:
            self.ignore_patterns = [os.path.normcase(pattern) for
                                    pattern in ignore_patterns]

        self.suffixes = suffixes
        self.failures = {}

    def handles(self, src, path):
        """Must return a list of files that this handler will produce after
        successfully processing `path`. If the current handler does not operate
        on `path`, None should be returned. If instead `path` should not
        produce output by itself (but should be compiled nonetheless), then an
        empty list should be returned. This function will be called every time
        the file identified by `path` changes (only the modification time is
        taken into account; `src` is provided for convenience; it allows direct
        access to the file's contents.."""
        if not pathtools.patterns.match_path(path, self.patterns,
                                             self.ignore_patterns):
            return None

        return self._outputs(src, path)

    def deleted(self, src, path):
        """Called whenever `path` is deleted from the source folder `src`."""

    def changed(self, src, path, dest):
        """Called whenever `path` is changed in the source folder `src`. `dest`
        is the output folder. The default implementation calls `build` after
        determining that the input file is newer than any of the outputs, or
        any of the outputs does not exist."""
        try:
            mtime = os.path.getmtime(os.path.join(src, path))
            self._build(src, path, dest, mtime)
        except EnvironmentError as e:
            logging.error("{0} is inaccessible: {1}".format(
                termcolor.colored(path, "yellow", attrs=["bold"]),
                e.args[0]
            ))

    def _outputs(self, src, path):
        return [path + suffix for suffix in self.suffixes]

    def _build(self, src, path, dest, mtime):
        """Calls `build` after testing that at least one output file (as
        returned by `_outputs()` does not exist or is older than `mtime`. If
        the build fails, the build time is recorded and no other builds will be
        attempted on `input` until this method is called with a larger mtime.
        """
        input_path = os.path.join(src, path)
        output_paths = [os.path.join(dest, output) for output in
                        self._outputs(src, path)]

        if path in self.failures and mtime <= self.failures[path]:
            # the input file was not modified since the last recorded failure
            # as such, assume that the task will fail again and skip it
            return

        for output in output_paths:
            try:
                if \
                        os.path.exists(output) and \
                        mtime <= os.path.getmtime(output):
                    # output file exists and is up to date; no need to trigger
                    # build on this file's expense
                    continue
            except EnvironmentError:
                # usually happens when the output file has been deleted in
                # between the call to exists and the call to getmtime
                pass

            start = time.time()
            try:
                self.build(input_path, output_paths)
            except Exception as e:
                if isinstance(e, EnvironmentError):
                    # non-zero return code in sub-process; only show message
                    logging.error("{0} failed after {1:.2f}s: {2}".format(
                        termcolor.colored(path, "red", attrs=["bold"]),
                        time.time() - start, e.args[0]
                    ))
                else:
                    # probably a bug in the handler; show full trace
                    logging.exception("{0} failed after {1:.2f}s".format(
                        termcolor.colored(path, "red", attrs=["bold"]),
                        time.time() - start
                    ))
                self.failures[path] = start
            else:
                logging.info("{0} completed in {1:.2f}s".format(
                    termcolor.colored(path, "green", attrs=["bold"]),
                    time.time() - start
                ))
                self.failures.pop(path, None)
            break

    def build(self, input_path, output_paths):
        """Should be extended by subclasses to actually do stuff. By default
        this will copy `input` over every file in the `outputs` list."""
        for output in output_paths:
            shutil.copy(input_path, output_paths)


_base_path = re.compile("///.*?<base\s+path=[\"\'](.*)[\"\']\s*/>", re.I)


class TreeHandler(Handler):
    def __init__(self, patterns, ignore_patterns=None, suffixes=[""],
                 line_regex=_base_path):
        """Creates a new tree handler. `line_regex` is a regex that determines
        whether a file is self-sufficient or must be included in one (or more)
        files."""
        super(TreeHandler, self).__init__(patterns, ignore_patterns, suffixes)

        self.line_regex = re.compile(line_regex)
        self.parents = {}  # maps a filename to a list of direct parents
        self.children = {}  # maps a filename to a list of direct children

    def rebuild_references(self, src, path, reject=None):
        """Updates `parents` and `children` to be in sync with the changes to
        `src` if any."""
        if reject is None:
            reject = set()
        reject.add(path)

        try:
            filename = os.path.join(src, path)
            mtime = os.path.getmtime(filename)
            contents = open(filename)
        except EnvironmentError:
            raise ValueError("Unable to open '{0}'".format(path))

        if \
                path in self.parents and \
                self.parents[path].updated == mtime:
            # cache hit; no need to update
            return

        # drop existing references
        if path in self.parents:
            self.deleted(src, path)

        # build a list of parents
        parents = TimedSet(mtime)
        current = os.path.dirname(path)

        for line in contents:
            match = self.line_regex.search(line)
            if match:
                parent = match.group(1)
                relative = os.path.normpath(os.path.join(current, parent))
                if relative.startswith(".."):
                    raise ValueError("Parent reference '{0}' outside of "
                                     "watched folder in '{1}'".format(parent,
                                                                      path))
                parent = os.path.normcase(relative)
                if parent in reject:
                    raise ValueError("Circular reference to '{0}' "
                                     "detected in '{1}'".format(parent,
                                                                path))
                parents.add(parent)

        for parent in parents:
            # recursively build references for all parents; this will
            # usually be a cache hit and no-op
            self.rebuild_references(src, parent, reject)

        self.parents[path] = parents
        for parent in parents:
            # add this node to each of its parents' children
            if parent not in self.children:
                self.children[parent] = set()
            self.children[parent].add(path)

    def handles(self, src, path):
        if \
                not pathtools.patterns.match_path(path, self.patterns,
                                                  self.ignore_patterns) and \
                path not in self.children:
            # allow both files that match the pattern as well as explicitly
            # defined parent files
            return None

        # rebuild references
        try:
            start = time.time()
            self.rebuild_references(src, path)
        except ValueError as e:
            # there was an error processing this file
            logging.error("{0} failed after {1:.2f}s: {1}".format(
                termcolor.colored(path, "red", attrs=["bold"]),
                time.time() - start, e.args[0]
            ))
            return None

        # only files that don't have any parent produce output via this handler
        if self.parents[path]:
            return []
        else:
            return self._outputs(src, path)

    def deleted(self, src, path):
        """Update the reference tree when a handled file is deleted."""
        if self.parents[path] is not None:
            for parent in self.parents[path]:
                self.children[parent].remove(path)
                if not self.children[parent]:
                    del self.children[parent]
        del self.parents[path]

    def changed(self, src, path, dest):
        """If `path` does not have any parents, it is built. Otherwise, it will
        attempt to build every parent of `path` (or their parents). Output file
        modification times are taken into account to prevent unnecessary
        builds."""
        modified = {path: self.parents[path].updated}

        while True:
            for path in modified:
                if self.parents[path]:
                    mtime = modified.pop(path)
                    for parent in self.parents[path]:
                        modified[parent] = max(mtime,
                                               self.parents[parent].updated)
                    break
            else:
                break

        for path in modified:
            self._build(src, path, dest, modified[path])
