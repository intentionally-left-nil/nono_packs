"""
Scenario 6: Network access.

Goal: Confirm outbound network is permitted by the profile.

Tests:

1. ``test_https_request`` — makes an HTTPS GET to https://example.com,
   asserts HTTP 200 and prints NETWORK_OK.
"""

from __future__ import annotations


# ---------------------------------------------------------------------------
# 1. HTTPS request to a well-known public endpoint
# ---------------------------------------------------------------------------


def test_https_request(sandbox):
    """
    The sandbox must allow outbound HTTPS connections.

    The profile sets ``network.block: false``, so urllib.request.urlopen
    must succeed against a stable public endpoint (example.com).

    Expected: exits 0, prints NETWORK_OK.
    """
    result = sandbox(
        """
        import urllib.request
        with urllib.request.urlopen("https://example.com", timeout=10) as r:
            assert r.status == 200, f"unexpected status: {r.status}"
        print("NETWORK_OK")
        """,
        timeout=60,
    )

    assert result.returncode == 0, (
        f"Expected exit 0 but got {result.returncode}.\n"
        f"stdout: {result.stdout!r}\n"
        f"stderr: {result.stderr!r}"
    )
    assert "NETWORK_OK" in result.stdout, (
        f"Marker NETWORK_OK not found in stdout.\n"
        f"stdout: {result.stdout!r}\n"
        f"stderr: {result.stderr!r}"
    )
