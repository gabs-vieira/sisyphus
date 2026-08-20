# Token bucket, keyed per domain. Controls **rate** — how many requests per
# second start against a target. Refill computed on demand from elapsed time,
# not by a background timer.

# Use `time.monotonic()`, not `time.time()` — the latter can jump backwards
# when the system clock adjusts, corrupting interval math.


# Reference to Study + Apply https://bytebytego.com/courses/system-design-interview/design-a-rate-limiter


class RateLimiter:

    def __init__(self) -> None:
        pass