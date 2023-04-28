import os
import sys
from datetime import datetime

from .step import steps


class ConsoleLoggingReporter:
    """ConsoleLoggingReporter - Reporter that writes console log files

    Args:
        logpath (str): path to store the logfiles in
    """
    instance = None

    @classmethod
    def start(cls, path):
        """starts the ConsoleLoggingReporter"""
        assert cls.instance is None
        cls.instance = cls(path)

    @classmethod
    def stop(cls):
        """stops the ConsoleLoggingReporter"""
        assert cls.instance is not None
        cls.instance._stop()
        steps.unsubscribe(cls.instance.notify)
        cls.instance = None

    def __init__(self, logpath):
        self._logcache = {}
        self.logpath = logpath
        if not os.path.exists(self.logpath):
            os.makedirs(self.logpath)
        steps.subscribe(self.notify)

    def _stop(self):
        while self._logcache:
            _, log = self._logcache.popitem()
            # ignore cache entries for errors
            if log is None:
                continue
            log.close()

    def get_logfile(self, event):
        """Returns the correct file handle from cache or creates a new file handle"""
        source = event.step.source
        try:
            log = self._logcache[source]
        except KeyError:
            if source.name:
                name = f'console_{source.target.name}_{source.name}'
            else:
                name = f'console_{source.target.name}'
            name = os.path.join(self.logpath, name)
            try:
                log = self._logcache[source] = open(name, mode='ab',
                                                    buffering=0)
            except OSError as e:
                print(f"failed to open log file {name}: {e}", file=sys.stderr)
                log = self._logcache[source] = None
            if not log:
                return None

            if source.name:
                log.write(
                    f"Labgrid Console Logfile for {source.target.name} {source.name}\n"
                    .encode("utf-8")
                )
            else:
                log.write(
                    f"Labgrid Console Logfile for {source.target.name}\n"
                    .encode("utf-8")
                )
            log.write(
                f"Logfile started at {datetime.now()}\n".encode("utf-8")
            )
            log.write("=== Log starts here ===\n".encode('utf-8'))

        return log

    def notify(self, event):
        """This is the callback function for steps"""
        step = event.step
        if step.tag == 'console':
            if step.title == 'read':
                if event.data.get('state') == 'stop':
                    if step.result and step.source:
                        log = self.get_logfile(event)
                        if not log:
                            return
                        log.write(step.result)
