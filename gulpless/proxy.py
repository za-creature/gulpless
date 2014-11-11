# coding=utf-8
from __future__ import absolute_import, unicode_literals, division

import watchdog.events
import os


class Proxy(watchdog.events.FileSystemEventHandler):
    def __init__(self, observer, path, change):
        super(Proxy, self).__init__()

        observer.schedule(self, path, True)
        self.path = path
        self._changed = change

        self.updated = True
        self.files = {}

    def on_any_event(self, event):
        """Called whenever a FS event occurs."""
        self.updated = True
        if self._changed:
            self._changed()

    def changes(self):
        """Collects all changes that have been performed on the monitored path,
        returning them as a (created, deleted) tuple."""
        deleted = []
        for path in list(self.files):
            isdir = path.endswith(os.sep)
            abspath = os.path.join(self.path, path)
            if not os.path.exists(abspath) or os.path.isdir(abspath) != isdir:
                deleted.append(path)
                del self.files[path]

        changed = []
        for folder, subfolders, subfiles in os.walk(self.path):
            for path in subfolders:
                path = os.path.join(folder, path)
                path = os.path.normcase(os.path.relpath(path, self.path))
                path += os.sep
                if path not in self.files:
                    # don't really care about folder mtime
                    self.files[path] = 0
                    changed.append(path)

            for path in subfiles:
                path = os.path.join(folder, path)
                mtime = os.path.getmtime(path)
                path = os.path.normcase(os.path.relpath(path, self.path))

                if path not in self.files:
                    # new file; set its mtime to 0 because it will be compared
                    # in the next few lines
                    self.files[path] = 0

                if mtime > self.files[path]:
                    # file has been changed since last check
                    self.files[path] = mtime
                    changed.append(path)

        self.updated = False
        return changed, deleted
