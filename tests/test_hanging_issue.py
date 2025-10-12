"""Test to reproduce the hanging issue in actual Django request flow."""

import asyncio
import threading
import time
from typing import Any
from unittest.mock import Mock
from unittest.mock import patch

import pytest
from django.test import Client
from django.urls import reverse

from search.browser_manager import get_browser_page
from search.models import SearchUser


@pytest.mark.django_db
class TestHangingIssue:
    """Test to reproduce and fix the hanging issue."""

    @pytest.fixture
    def authenticated_user(self) -> SearchUser:
        """Create an authenticated user."""
        return SearchUser.objects.create_user(username="admin", password="password")

    @pytest.fixture
    def authenticated_client(
        self, authenticated_user: SearchUser
    ) -> Client:  # pylint: disable=unused-argument
        """Create authenticated Django test client."""
        client = Client()
        client.login(username="admin", password="password")
        return client

    def test_search_request_does_not_hang(self, authenticated_client: Client) -> None:
        """Test that a search request completes within reasonable time."""
        # This test should complete within 10 seconds
        # If it hangs, the test will fail with timeout

        start_time = time.time()
        completed = threading.Event()
        exception_holder = []

        def make_request() -> None:
            try:
                response = authenticated_client.get(
                    reverse("index"), {"query": "test search"}
                )
                # We expect either success or redirect (if no results)
                assert response.status_code in [
                    200,
                    302,
                ], f"Unexpected status: {response.status_code}"
                completed.set()
            except (
                Exception
            ) as e:  # pylint: disable=broad-exception-caught  # noqa: BLE001
                exception_holder.append(e)
                completed.set()

        # Run request in separate thread to detect hanging
        thread = threading.Thread(target=make_request)
        thread.daemon = True
        thread.start()

        # Wait for completion or timeout after 10 seconds
        if not completed.wait(timeout=10.0):
            pytest.fail("Search request hung and did not complete within 10 seconds")

        end_time = time.time()
        duration = end_time - start_time

        # If there was an exception, re-raise it
        if exception_holder:
            raise exception_holder[0]

        print(f"Request completed in {duration:.2f} seconds")

    def test_concurrent_search_requests(self, authenticated_client: Client) -> None:
        """Test that multiple concurrent search requests don't deadlock."""
        num_requests = 3
        results = []
        exceptions = []

        def make_concurrent_request(query_id: int) -> None:
            try:
                response = authenticated_client.get(
                    reverse("index"), {"query": f"test search {query_id}"}
                )
                results.append((query_id, response.status_code))
            except (
                Exception
            ) as e:  # pylint: disable=broad-exception-caught  # noqa: BLE001
                exceptions.append((query_id, e))

        # Start multiple requests concurrently
        threads = []
        start_time = time.time()

        for i in range(num_requests):
            thread = threading.Thread(target=make_concurrent_request, args=(i,))
            thread.daemon = True
            threads.append(thread)
            thread.start()

        # Wait for all threads to complete
        for thread in threads:
            thread.join(timeout=15.0)  # 15 second timeout per thread
            if thread.is_alive():
                pytest.fail("Thread did not complete within timeout")

        end_time = time.time()
        duration = end_time - start_time

        # Check results
        if exceptions:
            pytest.fail(f"Exceptions occurred: {exceptions}")

        assert (
            len(results) == num_requests
        ), f"Expected {num_requests} results, got {len(results)}"
        print(
            f"All {num_requests} concurrent requests completed in {duration:.2f} seconds"
        )

    @patch("search.meta_search.fetch_results")
    def test_fetch_results_timeout_behavior(
        self, mock_fetch_results: Mock, authenticated_client: Client
    ) -> None:
        """Test behavior when fetch_results takes too long."""

        # Simulate a hanging fetch_results
        def slow_fetch_results(*args: Any, **kwargs: Any) -> list[Any]:
            time.sleep(2)  # Simulate slow response
            return [{"title": "Test Result", "url": "https://example.com"}]

        mock_fetch_results.side_effect = slow_fetch_results

        start_time = time.time()
        response = authenticated_client.get(reverse("index"), {"query": "test"})
        end_time = time.time()

        duration = end_time - start_time

        # Should complete even with slow fetch_results
        assert response.status_code in [200, 302]
        assert duration < 5.0, f"Request took too long: {duration:.2f} seconds"

        print(f"Request with slow fetch_results completed in {duration:.2f} seconds")

    def test_browser_manager_thread_safety(self) -> None:
        """Test that browser manager is thread-safe."""
        results = []
        exceptions = []

        async def _test_browser_manager_async() -> bool:
            """Async test of browser manager."""
            page = await get_browser_page()
            await page.goto("about:blank")
            content = await page.content()
            await page.close()
            return len(content) > 0

        def test_browser_access() -> None:
            try:
                # This simulates what happens in actual requests
                def run_test() -> bool:
                    return asyncio.run(_test_browser_manager_async())

                result = run_test()
                results.append(result)
            except (
                Exception
            ) as e:  # pylint: disable=broad-exception-caught  # noqa: BLE001
                exceptions.append(e)

        # Test concurrent access
        threads = []
        for _ in range(3):
            thread = threading.Thread(target=test_browser_access)
            thread.daemon = True
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join(timeout=10.0)
            if thread.is_alive():
                pytest.fail("Browser manager thread test hung")

        if exceptions:
            pytest.fail(f"Browser manager thread safety test failed: {exceptions}")

        assert len(results) == 3, f"Expected 3 results, got {len(results)}"
        assert all(results), "All browser manager tests should succeed"
