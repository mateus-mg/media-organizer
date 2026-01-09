"""
Rate limiter for controlling file operations and API calls
Implements semaphores for concurrency control and token bucket for API throttling
"""

import asyncio
import time
from typing import Optional
from contextlib import asynccontextmanager
from collections import defaultdict


class TokenBucket:
    """Token bucket implementation for rate limiting"""

    def __init__(self, rate: float):
        """
        Initialize token bucket

        Args:
            rate: Number of tokens per second
        """
        self.rate = rate
        self.tokens = rate
        self.last_update = time.time()
        self._lock = asyncio.Lock()

    async def acquire(self, tokens: int = 1) -> bool:
        """
        Acquire tokens from bucket

        Args:
            tokens: Number of tokens to acquire

        Returns:
            True if tokens acquired, False otherwise
        """
        async with self._lock:
            now = time.time()
            elapsed = now - self.last_update
            self.tokens = min(self.rate, self.tokens + elapsed * self.rate)
            self.last_update = now

            if self.tokens >= tokens:
                self.tokens -= tokens
                return True

            # Calculate wait time
            wait_time = (tokens - self.tokens) / self.rate
            await asyncio.sleep(wait_time)
            self.tokens = 0
            return True


class RateLimiter:
    """Global rate limiter for file operations and API calls"""

    def __init__(
        self,
        max_concurrent_file_ops: int = 3,
        max_concurrent_api_calls: int = 2,
        tmdb_rate_limit: float = 4.0,
        file_op_delay_ms: int = 100
    ):
        """
        Initialize rate limiter

        Args:
            max_concurrent_file_ops: Maximum concurrent file operations
            max_concurrent_api_calls: Maximum concurrent API calls
            tmdb_rate_limit: TMDB requests per second
            file_op_delay_ms: Delay between file operations in milliseconds
        """
        # Semaphores for concurrency control
        self.file_ops_semaphore = asyncio.Semaphore(max_concurrent_file_ops)
        self.api_calls_semaphore = asyncio.Semaphore(max_concurrent_api_calls)

        # Token buckets for API throttling
        self.tmdb_bucket = TokenBucket(tmdb_rate_limit)

        # File operation delay
        self.file_op_delay = file_op_delay_ms / 1000.0

        # Statistics
        self.stats = defaultdict(int)
        self._stats_lock = asyncio.Lock()

    @asynccontextmanager
    async def file_operation(self):
        """
        Context manager for rate-limited file operations

        Usage:
            async with rate_limiter.file_operation():
                # Perform file operation
                pass
        """
        async with self.file_ops_semaphore:
            async with self._stats_lock:
                self.stats['file_ops_total'] += 1

            try:
                yield
                # Add small delay between operations
                if self.file_op_delay > 0:
                    await asyncio.sleep(self.file_op_delay)
            finally:
                pass

    @asynccontextmanager
    async def api_call(self, service: str = 'tmdb'):
        """
        Context manager for rate-limited API calls

        Args:
            service: API service name ('tmdb')

        Usage:
            async with rate_limiter.api_call('tmdb'):
                # Make API call
                pass
        """
        async with self.api_calls_semaphore:
            # Acquire token from bucket (will wait if needed)
            await self.tmdb_bucket.acquire()

            async with self._stats_lock:
                self.stats[f'{service}_api_calls'] += 1

            try:
                yield
            finally:
                pass

    async def wait_if_needed(self, operation_type: str) -> float:
        """
        Check if rate limiting is needed and return wait time

        Args:
            operation_type: Type of operation ('file' or 'tmdb')

        Returns:
            Wait time in seconds (0 if no wait needed)
        """
        if operation_type == 'file':
            return self.file_op_delay

        # For API calls, check token availability
        async with self.tmdb_bucket._lock:
            now = time.time()
            elapsed = now - self.tmdb_bucket.last_update
            tokens = min(self.tmdb_bucket.rate,
                         self.tmdb_bucket.tokens + elapsed * self.tmdb_bucket.rate)

            if tokens >= 1:
                return 0.0
            else:
                return (1 - tokens) / self.tmdb_bucket.rate

    def get_stats(self) -> dict:
        """Get rate limiting statistics"""
        return dict(self.stats)

    def reset_stats(self):
        """Reset statistics"""
        self.stats.clear()


# Synchronous version for non-async code
class SyncRateLimiter:
    """Synchronous rate limiter for non-async contexts"""

    def __init__(
        self,
        max_concurrent_file_ops: int = 3,
        file_op_delay_ms: int = 100
    ):
        """
        Initialize synchronous rate limiter

        Args:
            max_concurrent_file_ops: Maximum concurrent file operations
            file_op_delay_ms: Delay between file operations in milliseconds
        """
        from threading import Semaphore

        self.file_ops_semaphore = Semaphore(max_concurrent_file_ops)
        self.file_op_delay = file_op_delay_ms / 1000.0
        self.stats = defaultdict(int)

    def file_operation(self):
        """
        Context manager for rate-limited file operations

        Usage:
            with rate_limiter.file_operation():
                # Perform file operation
                pass
        """
        return self._FileOpContext(self)

    class _FileOpContext:
        def __init__(self, limiter):
            self.limiter = limiter

        def __enter__(self):
            self.limiter.file_ops_semaphore.acquire()
            self.limiter.stats['file_ops_total'] += 1
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            if self.limiter.file_op_delay > 0:
                time.sleep(self.limiter.file_op_delay)
            self.limiter.file_ops_semaphore.release()

    def get_stats(self) -> dict:
        """Get rate limiting statistics"""
        return dict(self.stats)
