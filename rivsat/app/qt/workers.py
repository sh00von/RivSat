"""
QThread worker infrastructure.

A single generic `Worker` runs any callable off the UI thread and emits
signals for streaming log lines, progress, the final result, and errors.
Tabs connect these signals to their log console, progress bar, and result
rendering slots — keeping the GUI responsive during GEE downloads and
multi-core processing.
"""
import traceback
from PyQt6.QtCore import QThread, pyqtSignal, QObject


class WorkerSignals(QObject):
    log      = pyqtSignal(str)     # a log line (already timestamped by caller if desired)
    progress = pyqtSignal(int)     # 0-100
    finished = pyqtSignal(object)  # result payload (any type)
    error    = pyqtSignal(str)     # error message


class Worker(QThread):
    """
    Runs `fn(*args, log=<callable>, progress=<callable>, **kwargs)` in a thread.

    The target function may optionally accept `log` and `progress` keyword
    callables to stream updates back to the UI. If it doesn't accept them,
    pass `inject_callbacks=False`.
    """

    def __init__(self, fn, *args, inject_callbacks=True, **kwargs):
        super().__init__()
        self._fn      = fn
        self._args    = args
        self._kwargs  = kwargs
        self._inject  = inject_callbacks
        self.signals  = WorkerSignals()

    def run(self):
        try:
            if self._inject:
                self._kwargs.setdefault("log", self.signals.log.emit)
                self._kwargs.setdefault("progress", self.signals.progress.emit)
            result = self._fn(*self._args, **self._kwargs)
            self.signals.progress.emit(100)
            self.signals.finished.emit(result)
        except Exception as exc:  # noqa: BLE001 — surface everything to the UI
            tb = traceback.format_exc()
            self.signals.error.emit(f"{exc}\n\n{tb}")
