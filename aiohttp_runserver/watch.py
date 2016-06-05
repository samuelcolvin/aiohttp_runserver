import os
import signal

from fnmatch import fnmatch
from multiprocessing import Process
from datetime import datetime

from watchdog.events import PatternMatchingEventHandler, FileMovedEvent

from .common import logger
from .serve import serve_main_app

# specific to jetbrains I think, very annoying if not ignored
JB_BACKUP_FILE = '*___jb_???___'


class _BaseEventHandler(PatternMatchingEventHandler):
    patterns = ['*.*']
    ignore_directories = True
    ignore_patterns = [
        '*/.git/*',
        '*/include/python*',
        '*/lib/python*',
        '*/aiohttp_runserver/*',
        '*/.idea/*',
        JB_BACKUP_FILE,
    ]

    def __init__(self, aux_app, config, *args, **kwargs):
        self._app = aux_app
        self._config = config
        self._change_dt = datetime.now()
        self._since_change = None
        super().__init__(*args, **kwargs)

    def dispatch(self, event):
        if isinstance(event, FileMovedEvent):
            if fnmatch(event._src_path, JB_BACKUP_FILE) or fnmatch(event._dest_path, JB_BACKUP_FILE):
                return
        n = datetime.now()
        self._since_change = (n - self._change_dt).total_seconds()
        if self._since_change <= 1:
            logger.debug('%s | %0.3f seconds since last build, skipping', event, self._since_change)
            return
        self._change_dt = n
        return super().dispatch(event)


class CodeFileEventHandler(_BaseEventHandler):
    patterns = ['*.py']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._start_process()

    def on_any_event(self, event):
        logger.info('%s | %0.3f seconds since last build, restarting server', event, self._since_change)
        self.stop_process()
        self._start_process()

    def _start_process(self):
        self._process = Process(target=serve_main_app, kwargs=self._config)
        self._process.start()

    def stop_process(self):
        if self._process.is_alive():
            os.kill(self._process.pid, signal.SIGINT)
            self._process.join(5)
        else:
            logger.info('process already dead %s', self._process)


class StaticFileEventEventHandler(_BaseEventHandler):
    def on_any_event(self, event):
        self._app.static_reload(event.src_path)
