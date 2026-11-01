"""Async OpenRouter clients: rerank API (voyage) + decisions API (jev)."""
import asyncio
import collections
import os
import random
import time

import httpx

BASE = "https://openrouter.ai"
DEEPINFRA_BASE = "https://api.deepinfra.com/v1/inference"
RETRYABLE = {408, 409, 425, 429, 500, 502, 503, 504}


class FatalAPIError(Exception):
    pass


class TokenBucket:
    """Reserve-then-sleep bucket; safe under concurrent acquirers."""

    def __init__(self, rate_per_s: float, capacity: float):
        self.rate = rate_per_s
        self.cap = capacity
        self.tokens = capacity
        self.ts = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self, n: float):
        async with self._lock:
            now = time.monotonic()
            self.tokens = min(self.cap, self.tokens + (now - self.ts) * self.rate)
            self.ts = now
            self.tokens -= n
            wait = max(0.0, -self.tokens / self.rate)
        if wait:
            await asyncio.sleep(wait)


class Client:
    def __init__(self, concurrency: int = 64, timeout: float = 240.0, tries: int = 10):
        key = os.environ["OPENROUTER_API_KEY"]
        self._http = httpx.AsyncClient(
            base_url=BASE,
            headers={"Authorization": f"Bearer {key}",
                     "HTTP-Referer": "https://jev-reranker-bench",
                     "X-Title": "jev-reranker-bench"},
            timeout=httpx.Timeout(timeout, connect=30.0),
            limits=httpx.Limits(max_connections=concurrency * 2,
                                max_keepalive_connections=concurrency),
        )
        self.sem = asyncio.Semaphore(concurrency)
        self.tries = tries
        # HTTP outcome counters (status code / exception), for rate-limit evidence per run
        self.stats: collections.Counter = collections.Counter()
        # Voyage enforces a per-project TPM upstream (observed 2026-10-22: 12M/min for
        # rerank-2.5-lite via OpenRouter); this pacing is conservative, not the cap itself
        self.voyage_bucket = TokenBucket(rate_per_s=85_000, capacity=85_000)

    async def close(self):
        await self._http.aclose()

    async def _post(self, path: str, payload: dict, headers: dict | None = None):
        """Returns (json, latency_s). latency_s times only the final successful HTTP
        round-trip: it excludes the concurrency-semaphore wait and failed attempts, so it
        is the service latency, not the harness queueing time."""
        delay = 1.0
        last = None
        for t in range(self.tries):
            try:
                async with self.sem:
                    t0 = time.perf_counter()
                    r = await self._http.post(path, json=payload, headers=headers)
                    lat = time.perf_counter() - t0
                self.stats[r.status_code] += 1
                if r.status_code == 200:
                    return r.json(), lat
                body = r.text[:400]
                if r.status_code not in RETRYABLE:
                    raise FatalAPIError(f"{path} -> {r.status_code}: {body}")
                last = f"{r.status_code}: {body}"
            except (httpx.HTTPError, asyncio.TimeoutError) as e:
                self.stats[type(e).__name__] += 1
                last = repr(e)
            if t < self.tries - 1:
                await asyncio.sleep(delay * (0.5 + random.random()))
                delay = min(delay * 2, 90)
        raise FatalAPIError(f"{path} failed after {self.tries} tries: {last}")

    async def rerank(self, model: str, query: str, docs: list[str],
                     est_tokens: float = 10_000, pace: bool = False):
        """Returns (scores aligned with docs, latency_s, usage)."""
        if pace:
            await self.voyage_bucket.acquire(max(est_tokens, 1_000))
        j, lat = await self._post("/api/v1/rerank", {
            "model": model, "query": query, "documents": docs, "top_n": len(docs)})
        scores = [0.0] * len(docs)
        for r in j["results"]:
            scores[int(r["index"])] = float(r["relevance_score"])
        return scores, lat, j.get("usage") or {}

    async def rerank_deepinfra(self, model: str, query: str, docs: list[str]):
        """DeepInfra native reranker (outside OpenRouter). Returns (scores, latency_s, usage)."""
        j, lat = await self._post(f"{DEEPINFRA_BASE}/{model}", {"queries": [query], "documents": docs},
                                  headers={"Authorization": f"Bearer {os.environ['DEEPINFRA_API_KEY']}"})
        st = j.get("inference_status") or {}
        return ([float(s) for s in j["scores"]], lat,
                {"cost": st.get("cost"), "input_tokens": j.get("input_tokens") or st.get("tokens_input")})

    async def jev_choice(self, model: str, question: str, options: dict[str, str],
                         instructions: str):
        """options: {label: passage_text}. Returns (probs {label: p}, top_label, latency_s, usage)."""
        j, lat = await self._post("/api/alpha/decisions", {
            "model": model,
            "state": {"question": question},
            "questions": {"rank": {"type": "choice",
                                   "instructions": instructions,
                                   "criteria": options}},
        })
        ans = j["answers"]["rank"]
        probs = {k: float(v) for k, v in (ans.get("probabilities") or {}).items()}
        return probs, ans.get("choice"), lat, j.get("usage") or {}

    async def jev_noul_batch(self, model: str, question: str, passages: dict[str, str],
                             instructions: str):
        """Batched pointwise: one request, one independent noul question per passage.

        passages: {label: text}; instructions: template with {label}.
        Returns (probs {label: P(yes)}, latency_s, usage).
        """
        j, lat = await self._post("/api/alpha/decisions", {
            "model": model,
            "state": {"question": question, "passages": passages},
            "questions": {k: {"type": "noul", "instructions": instructions.format(label=k)}
                          for k in passages},
        })
        probs = {k: float(a["noul"]) for k, a in j["answers"].items()}
        return probs, lat, j.get("usage") or {}
