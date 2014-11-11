# coding=utf-8
from __future__ import absolute_import, unicode_literals, division

import pathtools.patterns
import logging
import shutil
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
        `suffixes` is a list of """
        super(Handler, self).__init__()

        self.patterns = patterns
        self.ignore_patterns = ignore_patterns
        self.suffixes = suffixes

    def _outputs(self, src, path):
        return [path + suffix for suffix in self.suffixes]

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

    def build(self, src, path, dest, outputs):
        """Must build `outputs` from `input`. This is always called *after* the
        source tree is up to date. The default implementation uses a cache to
        prevent supreflous """
        input_path = os.path.join(src, path)
        output_paths = [os.path.join(dest, output) for output in outputs]
        return self._build(self, input_path, output_paths)

    def _build(self, input, outputs):
        """Should be extended by subclasses to actually do stuff. By default
        this will copy `input` over every file in the `outputs` list."""
        logging.info("Building {0}".format(input))
        for output in outputs:
            shutil.copy(input, output)


_base_path = re.compile("///.*?<base\s+path=[\"\'](.*)[\"\']\s*/>", re.I)


class TreeHandler(Handler):
    def __init__(self, patterns, ignore_patterns=None, suffixes=[""],
                 line_regex=_base_path):
        """Creates a new tree handler. `line_regex` is a regex that determines
        whether a file is self-sufficient or must be included in one (or more)
        files."""
        super(Handler, self).__init__()

        self.patterns = patterns
        self.ignore_patterns = ignore_patterns
        self.suffixes = suffixes
        self.line_regex = re.compile(line_regex)

        self.parents = {}  # maps a filename to a list of direct parents
        self.children = {}  # maps a filename to a list of direct children

    def rebuild_references(self, src, path, reject=None):
        """Updates `parents` and `children` to be in sync with the changes to
        `src` if any."""
        try:
            if reject is None:
                reject = set()
            reject.add(path)

            try:
                filename = os.path.join(src, path)
                mtime = os.path.getmtime(filename)
                contents = open(filename)
            except IOError:
                raise ValueError("Unable to open '{0}'".format(path))

            if \
                    path in self.parents and \
                    self.parents[path].updated == mtime:
                # cache hit; no need to update
                return

            # drop existing references
            self.deleted(src, path)

            # build a list of parents
            self.parents[path] = parents = TimedSet(mtime)
            for line in contents:
                match = self.line_regex.search(line)
                if match:
                    parent = match.group(1)
                    current = os.path.dirname(path)
                    relative = os.path.normpath(os.path.join(current, parent))
                    if relative.startswith(".."):
                        raise ValueError("Parent reference '{0}' outside of "
                                         "watched folder in {1}".format(parent,
                                                                        path))
                    parent = os.path.normcase(relative)
                    if parent in reject:
                        raise ValueError("Circular reference to '{0}' "
                                         "detected in '{0}'".format(parent,
                                                                    path))
                    parents.add(parent)

            for parent in parents:
                # add this node to each of its parents' children
                if parent not in self.children:
                    self.children[parent] = set()
                self.children[parent].add(path)

                # recursively build references for all parents; this will
                # usually be a cache hit and no-op
                self.rebuild_references(src, parent, reject)
        except ValueError as e:
            logging.error(e.args[0])

    def handles(self, src, path):
        """Must return a list of files that this handler will produce after
        successfully processing `path`. If the current handler does not operate
        on `path`, or if `path` should not produce output, then an empty list
        should be returned. `contents` is a function that will return a file
        object that reads from the input file. This function will be called
        every time the file identified by `path` changes (only the modification
        time is taken into account; `contents` may still be the same)."""
        if \
                not pathtools.patterns.match_path(path, self.patterns,
                                                  self.ignore_patterns) and \
                path not in self.children:
            # allow both files that match the pattern as well as explicitly
            # defined parent files
            return None

        # rebuild references
        self.rebuild_references(src, path)
        if path not in self.parents:
            # there was an error processing this file
            return None

        if self.parents[path]:
            # file has a parent node and as such, it does not produce any
            # output files via this handler
            return []
        else:
            # file does not have a parent; as such, it produces output
            return self._outputs(src, path)

    def build(self, src, path, dest, outputs):
        """Must build `outputs` from `input`. The default implementation just
        copies the file to the destination(s)."""
        paths = {path: self.parents[path].updated}

        while True:
            for path in paths:
                if self.parents[path]:
                    mtime = paths.pop(path)
                    for parent in self.parents[path]:
                        paths[parent] = max(mtime,
                                            self.parents[parent].updated)
                    break
            else:
                break

        for path in paths:
            input_path = os.path.join(src, path)
            outputs = self._outputs(src, path)
            output_paths = [os.path.join(dest, output) for output in outputs]

            for output in output_paths:
                if os.path.getmtime(output) < paths[path]:
                    # cache invalidated; rebuild
                    self._build(input_path, output_paths)
                    break

    def deleted(self, src, path):
        """Previously handled input file deleted; rebuild references."""
        if path in self.parents:
            if self.parents[path] is not None:
                for parent in self.parents[path]:
                    self.children[parent].remove(path)
                    if not self.children[parent]:
                        del self.children[parent]
            del self.parents[path]
