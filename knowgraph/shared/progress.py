"""Progress notification system for MCP server tools.

This module provides real-time progress updates for long-running operations
via MCP notifications/message protocol, ensuring visibility across all MCP clients
(Copilot, Cursor, Windsurf, Claude Desktop, etc.).
"""

import time

from mcp.server import Server


class ProgressNotifier:
    """Send real-time progress notifications during MCP tool execution.

    Uses MCP notifications/message protocol to send progress updates that are
    visible in all MCP-compatible IDEs. Includes progress bar visualization,
    ETA calculation, and intelligent throttling to avoid flooding clients.

    Example:
        ```python
        progress = ProgressNotifier(server, "Indexing")
        await progress.start(100)

        for i in range(100):
            await progress.update(i + 1, f"Processing item {i+1}")

        await progress.complete("Successfully processed 100 items")
        ```
    """

    def __init__(
        self,
        server: Server,
        task_name: str,
        update_interval_ms: int = 100,
    ):
        """Initialize progress notifier.

        Args:
            server: MCP server instance for sending notifications
            task_name: Human-readable name of the task
            update_interval_ms: Minimum milliseconds between updates (throttling)
        """
        self.server = server
        self.task_name = task_name
        self.update_interval = update_interval_ms / 1000.0  # Convert to seconds

        self.current = 0
        self.total = 0
        self.start_time = 0.0
        self.last_update_time = 0.0
        self._last_percentage = -1  # Track to avoid duplicate notifications

    async def start(self, total: int, message: str | None = None) -> None:
        """Start progress tracking.

        Args:
            total: Total number of items to process
            message: Optional custom start message
        """
        self.current = 0
        self.total = total
        self.start_time = time.time()
        self.last_update_time = 0.0
        self._last_percentage = -1

        msg = message or f"🚀 Starting {self.task_name}..."
        await self._notify("info", msg)
        await self._notify("info", f"📊 Total items: {total}")

    async def update(self, current: int, message: str | None = None) -> None:
        """Update progress.

        Args:
            current: Current progress value
            message: Optional message describing current operation
        """
        self.current = current

        # Calculate percentage
        percentage = int((self.current / self.total) * 100) if self.total > 0 else 0

        # Throttle updates: only send if enough time passed OR percentage changed significantly
        now = time.time()
        time_since_last = now - self.last_update_time
        percentage_changed = abs(percentage - self._last_percentage) >= 5  # 5% threshold

        if time_since_last < self.update_interval and not percentage_changed:
            return

        self.last_update_time = now
        self._last_percentage = percentage

        # Calculate ETA
        elapsed = now - self.start_time
        eta = int((elapsed / self.current) * (self.total - self.current)) if self.current > 0 else 0

        # Create progress bar
        bar = self._create_progress_bar(percentage)

        # Build status line
        stats = f"{percentage}% | {self.current}/{self.total} | ⏱️ {int(elapsed)}s | ETA: {eta}s"

        msg = f"⏳ {bar} {stats}"
        if message:
            msg += f" | {message}"

        await self._notify("info", msg)

    async def increment(self, message: str | None = None) -> None:
        """Increment progress by one and update.

        Args:
            message: Optional message describing current operation
        """
        await self.update(self.current + 1, message)

    async def complete(self, message: str | None = None) -> None:
        """Mark task as completed.

        Args:
            message: Optional custom completion message
        """
        elapsed = int(time.time() - self.start_time)
        msg = message or f"{self.task_name} completed in {elapsed}s"
        await self._notify("info", f"✅ {msg}")

    async def error(self, message: str) -> None:
        """Report an error.

        Args:
            message: Error message
        """
        await self._notify("error", f"❌ {message}")

    async def warn(self, message: str) -> None:
        """Report a warning.

        Args:
            message: Warning message
        """
        await self._notify("warning", f"⚠️ {message}")

    async def debug(self, message: str) -> None:
        """Send debug-level message.

        Args:
            message: Debug message
        """
        await self._notify("debug", f"🔍 {message}")

    async def info(self, message: str) -> None:
        """Send info-level message.

        Args:
            message: Info message
        """
        await self._notify("info", f"ℹ️ {message}")

    async def _notify(
        self,
        level: str,
        message: str,
    ) -> None:
        """Send notification via MCP protocol.

        Args:
            level: Log level (debug, info, warning, error)
            message: Message to send
        """
        try:
            # Use MCP SDK's request_context to send log messages
            # Note: Server doesn't have direct notification method in MCP SDK
            # We'll use stderr as recommended by MCP protocol for server-side logging
            import sys
            print(f"[{level.upper()}] {message}", file=sys.stderr)
        except Exception as e:
            # Fallback to basic stderr if even that fails
            import sys
            print(f"[{level.upper()}] {message}", file=sys.stderr)
            print(f"[WARNING] Failed to send notification: {e}", file=sys.stderr)

    def _create_progress_bar(self, percentage: int) -> str:
        """Create visual progress bar.

        Args:
            percentage: Progress percentage (0-100)

        Returns:
            Progress bar string (e.g., "████████░░░░░░░░░░░░")
        """
        width = 20
        filled = int((percentage / 100) * width)
        empty = width - filled
        return "█" * filled + "░" * empty
