from pynisher.limiters.limiter import Limiter


class LimiterMac(Limiter):
    def limit_memory(self) -> None:
        """Limit's the memory of this process."""
        raise NotImplementedError()

    def limit_cpu_time(self) -> None:
        """Limit's the cpu time of this process."""
        raise NotImplementedError()

    def limit_wall_time(self) -> None:
        """Limit's the wall time of this process."""
        raise NotImplementedError()


class LimiterDarwin(Limiter):
    def limit_memory(self) -> None:
        """Limit's the memory of this process."""
        raise NotImplementedError()

    def limit_cpu_time(self) -> None:
        """Limit's the cpu time of this process."""
        raise NotImplementedError()

    def limit_wall_time(self) -> None:
        """Limit's the wall time of this process."""
        raise NotImplementedError()
