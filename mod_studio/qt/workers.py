"""
Background work, with signals instead of a queue of strings.

The Tkinter pages pass 33 distinct message kinds from worker threads to the
interface through a `queue.Queue` polled with `after()`:

    log, setup_progress, setup_done, setup_failed, nxd_ready, nxd_error,
    mod_sqlite_ready, table_progress, texture_export_done, sab_loaded, ...

A typo in any of those strings is not an error. The message is put on the
queue, the poller does not recognise it, and nothing happens - which looks
exactly like the work not having finished yet.

Declared signals make the same mistake fail at connect time, with the wrong
name or the wrong argument types. That is the whole reason for this module.

The engine is not touched to accommodate any of this. Its long-running
functions already take a `line_cb` callback, so a worker is a thin wrapper
that turns those callbacks into emissions.
"""
from __future__ import annotations

import traceback

from PySide6.QtCore import QObject, Qt, QThread, Signal


class Worker(QObject):
    """
    Base for a unit of background work.

    `run()` is what a subclass implements. Whatever happens in it, exactly
    one of `finished` or `failed` is emitted - a worker that ends silently
    leaves the page disabled forever, waiting for a message that will never
    arrive.
    """

    log = Signal(str)
    progress = Signal(int, int)      # done, total
    finished = Signal(object)
    failed = Signal(str)

    def run(self):
        raise NotImplementedError

    def start(self):
        try:
            result = self.run()
        except Exception as exc:                      # noqa: BLE001
            # The traceback goes to the log so a bug report has something in
            # it; the message goes to the interface so the user has
            # something readable.
            self.log.emit(traceback.format_exc())
            self.failed.emit(str(exc) or exc.__class__.__name__)
        else:
            self.finished.emit(result)


class CompareWorker(Worker):
    """Diffs two converted databases. Minutes of work on a large update."""

    def __init__(self, older_path, newer_path, older_label, newer_label):
        super().__init__()
        self.older_path, self.newer_path = older_path, newer_path
        self.older_label, self.newer_label = older_label, newer_label

    def run(self):
        from .. import migration
        self.log.emit(f"Comparing {self.older_label} with {self.newer_label}...")
        deltas = migration.compare_databases(self.older_path, self.newer_path)
        self.log.emit(f"Found differences in {len(deltas)} tables.")
        return deltas


def _must_be_a_bound_qobject_method(name, callback):
    """
    Rejects a callback Qt cannot place on the GUI thread.

    Qt decides which thread a slot runs on from the receiver's affinity, and
    it can only find a receiver if the callback is a bound method of a
    QObject. Give it a lambda or a plain function and there is no receiver,
    so the callback runs in whichever thread emitted - for a worker, the
    background one. A page handler that sets label text and enables buttons
    is then touching widgets off the GUI thread, which Qt does not allow.

    That failure is close to undetectable by reading the code. It does not
    raise. It shows up as a QTimer started in the callback never firing
    (the worker thread has no event loop), or as a crash somewhere
    unrelated, or as nothing at all until a user's machine is slower than
    the developer's. This project already knows what silent-wrong costs, so
    the wrong form is refused loudly at wiring time instead.
    """
    if callback is None:
        return
    receiver = getattr(callback, "__self__", None)
    if not isinstance(receiver, QObject):
        raise TypeError(
            f"{name} must be a bound method of a QObject so Qt can run it on "
            f"the GUI thread, not {callback!r}. A lambda or plain function "
            f"would be executed on the worker thread.")


class _RunningThreads(QObject):
    """
    Holds every started thread until it has actually stopped.

    `run_in_thread` used to return the QThread and tell the caller to keep a
    reference to it, which every page did the obvious way:

        self._thread = run_in_thread(...)

    One attribute, reused for every job on the page. That is wrong in two
    situations, and both crash the process rather than misbehaving:

    - **A handler that starts more work.** `SetupPage._unpacked` finishes an
      unpack and calls `adopt_existing_folder`, which assigns over
      `self._thread`. That assignment runs *inside* the `finished` handler,
      so it drops the last reference to the unpack thread while that thread
      is still in `exec()` - `quit()` is still sitting in the GUI thread's
      queue behind the very handler doing the dropping.

    - **Two jobs at once.** Nothing stops "Check for newer tables" being
      pressed during an unpack; the second `run_in_thread` overwrites the
      first thread the same way.

    Either way `~QThread` sees a running thread, prints "QThread: Destroyed
    while thread is still running" and aborts. Reproduced at SIGABRT before
    this class existed.

    A page cannot be expected to get this right - the correct version is a
    per-job collection that prunes itself, which is this. Threads are
    released on `finished`, so nothing accumulates: the set is empty again
    once the work is over.
    """

    def __init__(self):
        super().__init__()
        self._threads = set()

    def stop_all(self, milliseconds: int = 3000) -> None:
        """
        Asks every running thread to stop, and waits for it.

        Called when the application is quitting. Without it, closing the
        window while a worker is running leaves Python to destroy a live
        QThread during teardown - the same abort this class exists to
        prevent, arriving by a different route. Seen as
        "QThread: Destroyed while thread '' is still running" at the end of
        a test run that exited abruptly.

        `quit()` only ends the event loop, so a worker still inside `run()`
        finishes what it is doing first. The wait is bounded: a hung
        subprocess should not stop the application closing, and at that
        point the process is going away anyway.
        """
        for thread in list(self._threads):
            try:
                thread.quit()
                thread.wait(milliseconds)
            except RuntimeError:
                pass                       # Already gone; nothing to wait for.
        self._threads.clear()

    def hold(self, thread: QThread) -> None:
        self._threads.add(thread)
        # A bound method of this QObject, so a thread finishing on the
        # worker side is released on the GUI side. A lambda here would run
        # the release on the dying thread itself.
        thread.finished.connect(self.release)

    def release(self) -> None:
        # `sender()` rather than `isFinished()`: Qt emits `finished` just
        # BEFORE it sets the finished flag, so a fast queued delivery can
        # arrive while `isFinished()` is still False and leave the thread
        # held forever.
        thread = self.sender()
        if thread is not None:
            self._threads.discard(thread)

    def live_count(self) -> int:
        """How many threads are still running. Zero when the tool is idle."""
        return len(self._threads)


_running = None


def running_threads() -> _RunningThreads:
    """
    The registry, made on first use.

    Lazy because a QObject built at import time would take its thread
    affinity from whichever thread happened to import the module.
    """
    global _running
    if _running is None:
        _running = _RunningThreads()
    return _running


def run_in_thread(worker: Worker, on_finished=None,
                  on_failed=None, on_log=None, on_progress=None) -> QThread:
    """
    Puts a worker on its own thread and wires it up.

    Every callback must be a **bound method of a QObject** living in the GUI
    thread - in practice a method on the page. That is checked, not assumed.

    Connecting a signal to a plain Python function - a lambda, a bound
    method passed as a value - gives Qt no receiver to take thread affinity
    from, so the callback runs in whichever thread emitted the signal. For a
    worker that means **the callback runs on the worker thread**, and a page
    whose `_done` handler sets label text and enables buttons is then
    touching widgets from a background thread. Qt does not permit that. It
    does not usually raise either; it corrupts state, or crashes somewhere
    unrelated, or works for months and then doesn't.

    It also breaks quietly in a way that is easy to misread: a QTimer
    started inside such a callback never fires, because the worker thread
    has no event loop to run it. That is how this was found - the work
    plainly completed and the next step simply never happened.

    A bound method carries its object, so Qt finds the receiver, sees it
    belongs to the GUI thread, and queues the call there - which is where
    every one of these callbacks needs to run.

    Returns the QThread for convenience. **The caller does not have to keep
    it alive** - `_RunningThreads` does that until the thread has genuinely
    stopped.

    That used to be the caller's job, and the docstring here said so. It was
    the wrong place to put the responsibility: the natural way to discharge
    it, `self._thread = run_in_thread(...)`, is itself the bug as soon as a
    page runs two jobs or chains one onto another. See `_RunningThreads`.

    Both `finished` and `failed` quit the thread, so it is never left alive
    after the work is over.
    """
    thread = QThread()
    worker.moveToThread(thread)
    thread.started.connect(worker.start)

    # Before `started`, so a thread that finishes quickly is already held.
    running_threads().hold(thread)

    # The worker must outlive this function.
    #
    # Without this line nothing runs at all - and it fails in the most
    # confusing way available: `run()` is never called, no signal is ever
    # emitted, and neither `finished` nor `failed` arrives, so the page sits
    # disabled forever waiting on work that never began. No exception, no
    # warning until the thread is torn down.
    #
    # The cause is that the only Python reference to the worker is this
    # parameter. Connecting a bound method is not enough to keep it alive,
    # and once the wrapper is collected the underlying object goes with it,
    # so `started` has nothing left to call. Parenting it to the thread ties
    # its lifetime to something the caller already holds.
    thread._worker = worker

    # Every one of these goes through `context` so it lands on the GUI
    # thread. Connecting the callable alone would run it on the worker.
    for name, cb in (("on_log", on_log), ("on_progress", on_progress),
                     ("on_finished", on_finished), ("on_failed", on_failed)):
        _must_be_a_bound_qobject_method(name, cb)

    if on_log:
        worker.log.connect(on_log)
    if on_progress:
        worker.progress.connect(on_progress)
    if on_finished:
        worker.finished.connect(on_finished)
    if on_failed:
        worker.failed.connect(on_failed)

    worker.finished.connect(thread.quit)
    worker.failed.connect(thread.quit)
    thread.finished.connect(worker.deleteLater)

    thread.start()
    return thread
