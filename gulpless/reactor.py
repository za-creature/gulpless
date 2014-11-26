# coding=utf-8
from __future__ import absolute_import, unicode_literals, division
from gulpless.collector import Collector

import watchdog.observers
import logging
import time
import os


class Reactor(object):

    def __init__(self, src_path, dest_path, bundle=0.2, timeout=150):
        super(Reactor, self).__init__()

        self._src_path = os.path.normcase(os.path.abspath(src_path))
        self._dest_path = os.path.normcase(os.path.abspath(dest_path))

        self._observer = watchdog.observers.Observer()
        self._collector = Collector(self._observer,
                                    self._src_path, self._dest_path,
                                    bundle, timeout, self._batch)

        self._inputs = {}  # maps inputs to their list of outputs
        self._outputs = {}  # maps outputs to their input
        self._handlers = []  # a list of file handlers
        self._initial = True  # whether this is the first run or not
        self._once = False

    def add_handler(self, handler):
        self._handlers.append(handler)

    def start(self):
        self._collector.start()
        self._observer.start()
        self.running = True

    def stop(self):
        self._observer.stop()
        self._collector.stop()
        self.running = False

    def join(self, timeout=None):
        self._observer.join()
        self._collector.join()

    def run(self, once=False):
        """Runs the reactor in the main thread."""
        self._once = once
        self.start()
        while self.running:
            try:
                time.sleep(1.0)
            except KeyboardInterrupt:
                self.stop()
                self.join()

    def _parents(self, path):
        if path.endswith(os.sep):
            path = os.path.dirname(path)
        while True:
            path = os.path.dirname(path)
            if path in ("", os.sep):
                break
            yield path

    def _prepare_output(self, path):
        for segment in reversed(list(self._parents(path))):
            out = os.path.join(self._dest_path, segment)
            if os.path.exists(out) and not os.path.isdir(out):
                if segment in self._outputs:
                    raise ValueError("Invalid output structure: '{0}' is "
                                     "both a folder and a file".format(out))
                os.unlink(out)

            if not os.path.exists(out):
                os.mkdir(out)
            self._outputs[segment + os.sep] = True
        self._outputs[path] = True

    def _clean_output(self, path):
        # delete output file
        out = os.path.join(self._dest_path, path)
        if os.path.exists(out):
            os.unlink(out)

        # delete parent folders if possible
        for segment in self._parents(path):
            out = os.path.join(self._dest_path, segment)
            if os.path.exists(out):
                try:
                    os.rmdir(out)
                    del self._outputs[segment + os.sep]
                except OSError:
                    # current folder is not empty
                    break

    def _batch_dest(self, updated, deleted):
        for path in sorted(updated, key=len, reverse=True):
            if path not in self._outputs:
                # an unexpected file or folder was created in the output tree
                out = os.path.join(self._dest_path, path)
                if os.path.isdir(out):
                    os.rmdir(out)
                else:
                    os.unlink(out)

        for path in sorted(deleted, key=len):
            if path in self._outputs and path.endswith(os.sep):
                # an output folder was deleted; re-create
                out = os.path.join(self._dest_path, path)
                os.mkdir(out)

    def _batch_src(self, updated, deleted):
        for path in sorted(updated, key=len):
            if not path.endswith(os.sep):
                # if a previous version of the file was handled, remove all of
                # its outputs (and their folders, where possible)
                if path in self._inputs:
                    for handler, outputs in self._inputs[path]:
                        for out_path in outputs:
                            self._clean_output(out_path)

                # generate a list of all the handlers that can process the
                # current version of this file; for each handler, ensure that
                # it may safely output the files it's asking for
                self._inputs[path] = []
                for handler in self._handlers:
                    outputs = handler.handles(self._src_path, path)
                    if outputs is not None:
                        self._inputs[path].append((handler, outputs))
                        for out_path in outputs:
                            self._prepare_output(out_path)

                if self._inputs[path]:
                    # file can be processed by at least one handler
                    for handler, outputs in self._inputs[path]:
                        handler.changed(self._src_path, path, self._dest_path)
                else:
                    # no handlers accept the current version of this file
                    del self._inputs[path]

        for path in sorted(deleted, key=len, reverse=True):
            if path in self._inputs:
                # unlink all output files generated from this input
                for handler, outputs in self._inputs[path]:
                    handler.deleted(self._src_path, path)
                    for out_path in outputs:
                        self._clean_output(out_path)
                del self._inputs[path]

    def _batch(self, src_updated, src_deleted, dest_updated, dest_deleted):
        try:
            if self._initial:
                # the first run will yield all pre-existing files; we don't
                # want to delete any output files before we know whether we
                # actually need them or not
                self._batch_src(src_updated, src_deleted)
                self._batch_dest(dest_updated, dest_deleted)
                self._initial = False
                if self._once:
                    self.stop()
            else:
                # after the initial batch is complete and we have a list of
                # outputs, we'll delete first and ask questions later
                self._batch_dest(dest_updated, dest_deleted)
                self._batch_src(src_updated, src_deleted)

        except Exception:
            logging.exception("Run-time error")
            self.stop()
