"""
Scenario 7: Multiprocessing (ipc_mode: full).

Goal: Confirm that ``security.ipc_mode: full`` is set and that Python's
``multiprocessing`` module works inside the sandbox.  Missing or incorrect
``ipc_mode`` causes IPC/semaphore errors at runtime.

Tests:

1. ``test_pool_fork``       — multiprocessing.Pool with fork context maps a
                              function over 8 inputs and asserts correct results.
2. ``test_queue_roundtrip`` — multiprocessing.Queue round-trip via a forked
                              child process.
"""

from __future__ import annotations


# ---------------------------------------------------------------------------
# 1. multiprocessing.Pool with fork start method
# ---------------------------------------------------------------------------


def test_pool_fork(sandbox):
    """
    A fork-mode Pool must be able to map a worker function across inputs.

    The ``fork`` context is used explicitly to avoid spawn-mode overhead and to
    exercise the IPC primitives (semaphores, shared memory) that require
    ``security.ipc_mode: full``.

    Expected: exits 0, prints MULTIPROCESSING_OK, completes in under 5 seconds.
    """
    result = sandbox(
        """
        import multiprocessing, time
        def sq(x): return x * x
        start = time.monotonic()
        with multiprocessing.get_context("fork").Pool(4) as p:
            result = p.map(sq, range(8))
        assert result == [0, 1, 4, 9, 16, 25, 36, 49], result
        assert time.monotonic() - start < 5.0, "pool took too long"
        print("MULTIPROCESSING_OK")
        """,
        timeout=60,
    )

    assert result.returncode == 0, (
        f"Expected exit 0 but got {result.returncode}.\n"
        f"stdout: {result.stdout!r}\n"
        f"stderr: {result.stderr!r}"
    )
    assert "MULTIPROCESSING_OK" in result.stdout, (
        f"Marker MULTIPROCESSING_OK not found in stdout.\n"
        f"stdout: {result.stdout!r}\n"
        f"stderr: {result.stderr!r}"
    )


# ---------------------------------------------------------------------------
# 2. multiprocessing.Queue round-trip
# ---------------------------------------------------------------------------


def test_queue_roundtrip(sandbox):
    """
    A forked child process must be able to put a value on a Queue and the
    parent must be able to retrieve it.

    This exercises shared-memory and IPC primitives beyond just fork — it
    requires semaphores and pipes/sockets that depend on ``ipc_mode: full``.

    Expected: exits 0, prints QUEUE_OK.
    """
    result = sandbox(
        """
        import multiprocessing
        def producer(q): q.put("ping")
        ctx = multiprocessing.get_context("fork")
        q = ctx.Queue()
        p = ctx.Process(target=producer, args=(q,))
        p.start(); p.join()
        assert q.get() == "ping"
        print("QUEUE_OK")
        """,
        timeout=60,
    )

    assert result.returncode == 0, (
        f"Expected exit 0 but got {result.returncode}.\n"
        f"stdout: {result.stdout!r}\n"
        f"stderr: {result.stderr!r}"
    )
    assert "QUEUE_OK" in result.stdout, (
        f"Marker QUEUE_OK not found in stdout.\n"
        f"stdout: {result.stdout!r}\n"
        f"stderr: {result.stderr!r}"
    )
