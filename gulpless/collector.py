# coding=utf-8
from __future__ import absolute_import, unicode_literals, division
from gulpless.proxy import Proxy

import threading
import datetime


class Collector(threading.Thread):
    def __init__(self, observer, src_path, dest_path, bundle, timeout, batch):
        super(Collector, self).__init__()

        self.src_proxy = Proxy(observer, src_path, self.on_change)
        self.dest_proxy = Proxy(observer, dest_path, self.on_change)

        self.bundle = datetime.timedelta(seconds=bundle)
        self.timeout = datetime.timedelta(seconds=timeout)
        self.batch = batch

        self.running = True
        self.lock = threading.Condition()
        self.wakeup = datetime.datetime.now()

    def timedelta(self):
        now = datetime.datetime.now()
        td = self.wakeup - now
        micro = td.microseconds + (td.seconds + td.days * 24 * 3600) * 10**6
        return now, micro / 10**6

    def run(self):
        while self.running:
            with self.lock:
                # wait until `wakeup` is in the past or we died
                while self.running:
                    now, delta = self.timedelta()
                    if delta > 0:
                        self.lock.wait(delta)
                    else:
                        self.wakeup = now + self.timeout
                        break

                if not self.src_proxy.updated and not self.dest_proxy.updated:
                    # no changes to be applied; do nothing
                    continue

            # collect events
            src_updated, src_deleted = self.src_proxy.changes()
            dest_updated, dest_deleted = self.dest_proxy.changes()

            # process current batch while blocking this thread
            self.batch(src_updated, src_deleted, dest_updated, dest_deleted)

    def stop(self):
        with self.lock:
            self.running = False
            self.lock.notify()

    def on_change(self):
        with self.lock:
            self.wakeup = datetime.datetime.now() + self.bundle
            self.lock.notify()
