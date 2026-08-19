# Resilient Collector

A data collection system built around one question: **how do you keep
collecting when the target pushes back — and how do you know the moment
you've stopped?**

The scraping itself is the easy part. What makes this a system rather than
a script is the layer around it: per-target pacing, identity rotation with
health scoring, retry classification, and a live dashboard that surfaces
failure *including the silent kind*.

**Live dashboard:** _(link goes here once deployed)_

---

## Why this exists

A naive scraper works for ten minutes. Then it gets rate-limited, or the
site changes its markup, or the process dies at 3am and nobody notices.
Most scraping projects solve the first ten minutes. This one is about
everything after.

The collection target (`books.toscrape.com`) is deliberately a sandbox
published for scraping practice — running a 24/7 demo against someone
else's production site would be a real problem no matter how good the code
is. The target is the test case; the resilience layer is the point.

---

## Architecture

```
                    ┌──────────────────┐
                    │     Scheduler    │  runs every N minutes
                    └────────┬─────────┘
                             ▼
   ┌──────────────────────────────────────────────────┐
   │                     Runner                       │
   │                                                  │
   │   IdentityPool ──► pick healthiest identity      │
   │        │                                         │
   │   Semaphore ─────► cap concurrent per domain     │
   │        │                                         │
   │   RateLimiter ───► cap requests/sec per domain   │
   │        │                                         │
   │   Retry ─────────► backoff + jitter, classified  │
   │        │                                         │
   │   Collector ─────► fetch + parse target          │
   │        │                                         │
   │   Quality ───────► field completeness check      │
   │        │                                         │
   │   Metrics ───────► outcomes per domain           │
   └────────┬─────────────────────────────────────────┘
            ▼
    ┌───────────────┐         ┌──────────────────┐
    │    Storage    │────────►│    Dashboard     │
    │  (run history)│         │  (live metrics)  │
    └───────────────┘         └──────────────────┘
```

---

## Structure

```
resilient-collector/
├── src/
│   ├── core/                 # target-agnostic resilience primitives
│   │   ├── identity.py       # Identity + IdentityPool
│   │   ├── rate_limiter.py   # token bucket, per domain
│   │   ├── retry.py          # backoff + jitter + error classification
│   │   └── metrics.py        # outcome counters, per domain
│   ├── collectors/           # target-specific logic
│   │   ├── base.py           # interface every collector implements
│   │   └── books.py          # books.toscrape.com
│   ├── quality/
│   │   └── completeness.py   # data-quality checks
│   ├── storage/
│   │   └── repository.py     # persist + read run history
│   ├── dashboard/
│   │   └── app.py            # web view over stored runs
│   └── runner.py             # wires everything, entrypoint
├── tests/
│   └── fixtures/             # saved HTML — tests never hit the network
├── infra/                    # IaC (phase 5)
└── requirements.txt
```

### Why this split

`core/` knows nothing about books, or HTML, or any specific site. Adding a
second target means writing one file in `collectors/` and touching nothing
else — that's the test of whether the boundary is real.

`collectors/` is the only place that knows what a target's markup looks
like, which is also the only place that breaks when the target redesigns.

---

## Module responsibilities

Build these in order. Each one is small enough to write and test on its own.

### `core/identity.py`
An **Identity** is a persona: a proxy plus a fingerprint (headers), carrying
a success/failure history. An **IdentityPool** manages them as a resource —
hands out the healthiest, retires ones falling below a threshold, and
recovers rather than deadlocking if everything is burned.

Decide: how do you score health? Does an identity with 10,000 old successes
and 50 recent failures look healthy? (Hint: sliding window.)

### `core/rate_limiter.py`
Token bucket, keyed per domain. Controls **rate** — how many requests per
second start against a target. Refill computed on demand from elapsed time,
not by a background timer.

Use `time.monotonic()`, not `time.time()` — the latter can jump backwards
when the system clock adjusts, corrupting interval math.

### `core/retry.py`
Two decisions: *is this worth retrying?* and *how long to wait?*

Classify before retrying — `429`/`503` are transient, `404` is not, and
retrying it is pure waste. Delay doubles per attempt, capped, plus jitter so
that N workers failing simultaneously don't all wake at the same instant.

### `core/metrics.py`
Counters **per domain and per outcome**, never a single global number. A
5% aggregate error rate hides a domain at 80% when ten others are at zero.

### `collectors/base.py`
The contract every collector fulfils: which URLs to fetch, and how to turn
a response into records. Keeping this explicit is what lets `runner.py`
treat all targets identically.

### `collectors/books.py`
Parses `books.toscrape.com` listings. Each card is
`<article class="product_pod">` with title, price, availability, rating.

Parse **defensively**: a missing node yields an empty value, not an
exception. When markup changes you want one field to degrade, not the whole
run to die — and the empty value then shows up in completeness.

### `quality/completeness.py`
Percentage of non-empty values per field.

This catches the worst class of scraping bug: the site changes its markup,
the parser keeps running without error, HTTP returns 200, and you quietly
store thousands of empty records. **A dashboard watching only status codes
would show 100% success while the data is garbage.**

### `storage/repository.py`
Persists each run and reads back history. Start with SQLite locally; the
interface should be narrow enough that swapping to DynamoDB later touches
this file only.

### `dashboard/app.py`
Serves the stored history as a page. Success/block rate over time, identity
health, completeness per field, throughput.

### `runner.py`
Orchestration only — no business logic of its own. Picks identity, applies
semaphore and rate limiter, calls the collector through retry, records
metrics, computes quality, persists the run.

---

## Roadmap

Each phase ends with something you run and see. Don't start the next until
the current one works.

### Phase 1 — Collector
- [ ] `core/` primitives with unit tests
- [ ] `collectors/books.py` with a saved HTML fixture
- [ ] `quality/completeness.py`
- [ ] `runner.py` producing a structured run result

**Done when:** `python -m src.runner` prints collected records, per-domain
metrics, identity health, and field completeness.

### Phase 2 — Persistence
- [ ] `storage/repository.py` with SQLite
- [ ] Runner writes each run

**Done when:** running twice shows two rows of history.

### Phase 3 — Dashboard
- [ ] `dashboard/app.py` reading from storage
- [ ] Charts: outcomes over time, identity health, completeness

**Done when:** `localhost:8000` shows real numbers that change after a run.

### Phase 4 — Packaging
- [ ] Dockerfile
- [ ] CI running tests on push

**Done when:** the container runs the same locally as bare Python.

### Phase 5 — Deploy
- [ ] Storage swapped to DynamoDB
- [ ] Collector on Lambda, scheduled
- [ ] Dashboard on a Lambda Function URL

**Done when:** the public URL shows data collected without your laptop on.

---

## Design decisions

Written down because being able to defend them matters more than having
made them.

**Semaphore *and* token bucket, not one or the other.** They constrain
different things. The bucket limits how many requests per second *start*;
the semaphore limits how many are *in flight*. At 2 req/s with 8-second
responses, you accumulate ~16 open connections while never breaking the
rate limit. Only the semaphore catches that.

**Retry classifies before retrying.** A `404` is not going to become a
`200`. Retrying non-transient errors burns budget — and against a paid
proxy, burns money — for a guaranteed failure.

**Metrics are per-domain.** Aggregates hide exactly the failures worth
finding.

**Data quality is a first-class metric, not an afterthought.** HTTP success
and data success are different things, and only one of them is what you
actually wanted.

**Lambda for deployment, not ECS.** The load here is scheduled and small,
which is the profile where Lambda wins — and Lambda and DynamoDB have
permanent monthly free allowances while Fargate has no free tier at all.
The ECS design belongs to sustained high volume; picking by load profile
rather than by habit is the point.

---

## Running it

```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt

pytest tests/ -v          # tests run offline against fixtures
python -m src.runner      # one collection cycle
```

---

## Limitations

Stated deliberately — knowing where a system stops being true is part of
building it.

- The target has no anti-bot layer, so the identity/rotation machinery is
  exercised but never genuinely stressed.
- No real proxies: `Identity` carries the field, but requests go direct.
- Single-process state — two runners would not share identity health.
  Phase 5 moves that to DynamoDB.
