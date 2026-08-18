import inspect
import trio
import httpx
import holehe.core as holehe_core
from PyQt6.QtCore import QThread, pyqtSignal

class HoleheWorker(QThread):
    """Background worker that runs holehe checks in a separate Trio event loop.

    Signals:
        resultReady(dict): emitted for each individual result dict.
        progress(int, int): emitted after each site check (completed, total).
        finished_ok(list, float): emitted when all checks finish successfully.
        failed(str): emitted if discovery or setup fails.
    """

    resultReady = pyqtSignal(dict)
    progress = pyqtSignal(int, int)
    finished_ok = pyqtSignal(list, float)
    failed = pyqtSignal(str)

    def __init__(self, email: str):
        super().__init__()
        self.email = email
        self._cancel_scope = None
        self._trio_token = None
        self._results = []
        self._completed = 0
        self._total = 0
        self._start_time = None

    def run(self):
        try:
            trio.run(self._scan)
        except Exception as e:
            # Unexpected error in the Trio run
            self.failed.emit(str(e))

    async def _scan(self):
        """Discover check functions (including custom ones), run them concurrently, and emit signals.
        """
        self._start_time = trio.current_time()
        # Discover check functions from holehe and optional custom package
        check_funcs = self._discover_check_functions()
        self._total = len(check_funcs)
        if self._total == 0:
            self.failed.emit("No check functions discovered.")
            return

        # Capture the Trio token early so `stop()` works even if client setup fails
        self._trio_token = trio.lowlevel.current_trio_token()
        async with httpx.AsyncClient() as client:
            async with trio.open_nursery() as nursery:
                self._cancel_scope = nursery.cancel_scope
                for name, func in check_funcs:
                    nursery.start_soon(self._run_check, name, func, client)
                # The nursery will exit when all checks are done or cancelled

        elapsed = trio.current_time() - self._start_time
        self.finished_ok.emit(self._results, elapsed)

    def _discover_check_functions(self):
        """Return a list of (short_name, coroutine) for holehe and custom checks.

        The function attempts to import a local ``custom_checks`` package. If present,
        its modules are added to the discovery sources alongside ``holehe.modules``.
        """
        sources = ["holehe.modules"]
        try:
            import custom_checks  # noqa: F401 – ensure package is importable
            sources.append("custom_checks")
        except ImportError:
            pass

        check_funcs: list[tuple[str, object]] = []
        for source in sources:
            modules = holehe_core.import_submodules(source)
            for mod in modules.values():
                short_name = mod.__name__.split('.')[-1]
                func = getattr(mod, short_name, None)
                if func and inspect.iscoroutinefunction(func):
                    check_funcs.append((short_name, func))
        return check_funcs

    async def _run_check(self, name: str, func, client):
        """Execute a single holehe check function and emit its results.
        """
        out = []
        try:
            await func(self.email, client, out)
        except Exception as exc:
            # Synthesize a minimal error result so UI can display it
            out.append({
                "name": name,
                "domain": getattr(func, "domain", ""),
                "method": "",
                "frequent_rate_limit": False,
                "rateLimit": False,
                "exists": False,
                "emailrecovery": None,
                "phoneNumber": None,
                "others": str(exc),
            })
        for item in out:
            self._results.append(item)
            self.resultReady.emit(item)
        # Update progress
        self._completed += 1
        self.progress.emit(self._completed, self._total)

    def stop(self):
        """Request cancellation of the running Trio nursery.
        This method is safe to call from the GUI thread.
        """
        if self._cancel_scope and self._trio_token:
            # Use run_sync_soon to schedule cancellation from another OS thread
            self._trio_token.run_sync_soon(self._cancel_scope.cancel)
