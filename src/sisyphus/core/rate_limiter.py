# Token bucket, keyed per domain. Controls **rate** — how many requests per
# second start against a target. Refill computed on demand from elapsed time,
# not by a background timer.


# Use `time.monotonic()`, not `time.time()` — the latter can jump backwards
# when the system clock adjusts, corrupting interval math.




# Reference to Study + Apply https://bytebytego.com/courses/system-design-interview/design-a-rate-limiter

# Prevent resource starvation
# DDoS
# Reduce cost (limit excess requests) --> allocating more resources to high priority APIs.
# Prevent servers from beign overloaded





"""
type of rate limit that I want to implement: Server Side API Rate Limiter
    client-side: code running locally (user's device)
    server-side: remote computer/server, handling the business logic and etc

- rate limiter should be flexible to suuport diff sets of throttle rules
- handle large number of requests
-


"""

class RateLimiter:


   def __init__(self) -> None:
       pass

