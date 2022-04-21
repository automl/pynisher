from pynisher.limiters.limiter import Limiter


class LimiterWindows(Limiter):
    def limit_memory(self, memory: int) -> None:
        """Limit's the memory of this process."""
        self._raise_warning("Currently `limit_memory` not implemented on Windows")

    def limit_cpu_time(self, cpu_time: int, grace_period: int = 1) -> None:
        """Limit's the cpu time of this process."""
        self._raise_warning("Currently `limit_cpu_time` not implemented on Windows")

    def limit_wall_time(self, wall_time: int) -> None:
        """Limit's the wall time of this process."""
        self._raise_warning("Currently `wall_time` not implemented on Windows")

    def _try_remove_memory_limit(self) -> bool:
        """Remove memory limit if it can"""
        return False
