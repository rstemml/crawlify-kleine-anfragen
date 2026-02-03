"""Progress tracking and metrics display for CLI commands."""
from __future__ import annotations

import sys
import time
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class FetchProgress:
    """Track progress for fetch operations with pagination."""

    total_expected: Optional[int] = None
    pages_done: int = 0
    items_done: int = 0
    start_time: float = field(default_factory=time.time)
    last_page_time: float = field(default_factory=time.time)

    def update(self, items_in_page: int, total_from_api: Optional[int] = None) -> None:
        """Update progress after fetching a page."""
        self.pages_done += 1
        self.items_done += items_in_page
        if total_from_api is not None:
            self.total_expected = total_from_api
        self.last_page_time = time.time()

    def elapsed(self) -> float:
        """Total elapsed time in seconds."""
        return time.time() - self.start_time

    def items_per_second(self) -> float:
        """Average items fetched per second."""
        elapsed = self.elapsed()
        if elapsed == 0:
            return 0
        return self.items_done / elapsed

    def eta_seconds(self) -> Optional[float]:
        """Estimated time remaining in seconds."""
        if self.total_expected is None or self.items_done == 0:
            return None
        remaining = self.total_expected - self.items_done
        rate = self.items_per_second()
        if rate == 0:
            return None
        return remaining / rate

    def format_time(self, seconds: float) -> str:
        """Format seconds as human-readable time."""
        if seconds < 60:
            return f"{seconds:.0f}s"
        elif seconds < 3600:
            mins = int(seconds // 60)
            secs = int(seconds % 60)
            return f"{mins}m {secs}s"
        else:
            hours = int(seconds // 3600)
            mins = int((seconds % 3600) // 60)
            return f"{hours}h {mins}m"

    def print_status(self) -> None:
        """Print current status line (overwrites previous line)."""
        elapsed = self.elapsed()
        rate = self.items_per_second()

        parts = [f"[Page {self.pages_done}]"]
        parts.append(f"{self.items_done:,} items")

        if self.total_expected:
            pct = (self.items_done / self.total_expected) * 100
            parts.append(f"({pct:.1f}%)")

        parts.append(f"| {rate:.1f} items/s")
        parts.append(f"| {self.format_time(elapsed)}")

        eta = self.eta_seconds()
        if eta is not None and eta > 0:
            parts.append(f"| ETA: {self.format_time(eta)}")

        line = " ".join(parts)
        # Clear line and print status
        sys.stdout.write(f"\r\033[K{line}")
        sys.stdout.flush()

    def print_summary(self) -> None:
        """Print final summary on new line."""
        elapsed = self.elapsed()
        rate = self.items_per_second()
        print(f"\nDone: {self.items_done:,} items in {self.format_time(elapsed)} | {rate:.1f} items/s")


@dataclass
class NormalizeProgress:
    """Track progress for normalize operations."""

    total_files: int = 0
    files_done: int = 0
    items_new: int = 0
    items_updated: int = 0
    items_skipped: int = 0
    start_time: float = field(default_factory=time.time)

    def update(self, new: int = 0, updated: int = 0, skipped: int = 0) -> None:
        """Update counts after processing items."""
        self.items_new += new
        self.items_updated += updated
        self.items_skipped += skipped

    def file_done(self) -> None:
        """Mark a file as processed."""
        self.files_done += 1

    def elapsed(self) -> float:
        """Total elapsed time in seconds."""
        return time.time() - self.start_time

    def format_time(self, seconds: float) -> str:
        """Format seconds as human-readable time."""
        if seconds < 60:
            return f"{seconds:.0f}s"
        elif seconds < 3600:
            mins = int(seconds // 60)
            secs = int(seconds % 60)
            return f"{mins}m {secs}s"
        else:
            hours = int(seconds // 3600)
            mins = int((seconds % 3600) // 60)
            return f"{hours}h {mins}m"

    def print_status(self) -> None:
        """Print current status line."""
        total = self.items_new + self.items_updated + self.items_skipped
        if self.total_files > 0:
            pct = (self.files_done / self.total_files) * 100
            line = f"\r\033[K[{self.files_done}/{self.total_files}] ({pct:.0f}%) | {total:,} items processed"
        else:
            line = f"\r\033[K[{self.files_done} files] | {total:,} items processed"
        sys.stdout.write(line)
        sys.stdout.flush()

    def print_summary(self) -> None:
        """Print final summary."""
        elapsed = self.elapsed()
        total = self.items_new + self.items_updated + self.items_skipped
        print(f"\nDone: {total:,} items in {self.format_time(elapsed)}")
        print(f"  New: {self.items_new:,} | Updated: {self.items_updated:,} | Skipped: {self.items_skipped:,}")
