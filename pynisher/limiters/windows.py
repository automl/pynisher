from pynisher.limiters.limiter import Limiter


class LimiterWindows(Limiter):
    def limit_memory(self, memory: int) -> None:
        """Limit's the memory of this process."""
        raise NotImplementedError()

    def limit_cpu_time(self, cpu_time: int, grace_period: int = 0) -> None:
        """Limit's the cpu time of this process."""
        raise NotImplementedError()

    def limit_wall_time(self, wall_time: int) -> None:
        """Limit's the wall time of this process."""
        raise NotImplementedError()
