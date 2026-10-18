"""Простая нагрузочная проверка REST API MATCH (Этап 22, ADR-0028).

Запускается вручную против работающего API (uvicorn). Зависимость — `httpx`
(уже есть в dev-зависимостях `services/api`).

Примеры:

    # 500 GET /health при 20 параллельных запросах
    services\\api\\.venv\\Scripts\\python.exe scripts/loadtest.py \
        --base-url http://localhost:8000 --requests 500 --concurrency 20

    # проверить лимитер: 100 POST /drafts подряд при лимите 10/мин
    services\\api\\.venv\\Scripts\\python.exe scripts/loadtest.py \
        --method POST --path /api/v1/conversations/<id>/drafts \
        --token <access-token> --requests 100 --concurrency 10

Скрипт печатает rps, перцентили задержки и распределение статусов.
"""

from __future__ import annotations

import argparse
import asyncio
import statistics
import time

import httpx


def percentile(values: list[float], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, int(round(fraction * (len(ordered) - 1))))
    return ordered[index]


async def one(client: httpx.AsyncClient, method: str, path: str, body: bytes | None) -> tuple[int, float]:
    started = time.perf_counter()
    try:
        response = await client.request(method, path, content=body)
        status = response.status_code
    except httpx.HTTPError:
        status = 0
    return status, (time.perf_counter() - started) * 1000.0


async def run(args: argparse.Namespace) -> int:
    headers = {"Accept": "application/json"}
    if args.token:
        headers["Authorization"] = f"Bearer {args.token}"
    if args.body:
        headers["Content-Type"] = "application/json"
    body = args.body.encode("utf-8") if args.body else None

    semaphore = asyncio.Semaphore(args.concurrency)
    results: list[tuple[int, float]] = []

    async with httpx.AsyncClient(
        base_url=args.base_url.rstrip("/"), headers=headers, timeout=args.timeout
    ) as client:

        async def worker(index: int) -> None:
            async with semaphore:
                results.append(await one(client, args.method, args.path, body))

        started = time.perf_counter()
        await asyncio.gather(*(worker(i) for i in range(args.requests)))
        elapsed = time.perf_counter() - started

    latencies = [latency for _, latency in results]
    statuses: dict[int, int] = {}
    for status, _ in results:
        statuses[status] = statuses.get(status, 0) + 1

    ok = sum(count for status, count in statuses.items() if 200 <= status < 400)
    print(f"URL:          {args.method} {args.base_url}{args.path}")
    print(f"Запросов:     {len(results)} (параллельно {args.concurrency})")
    print(f"Время:        {elapsed:.2f} с")
    print(f"Пропускная:   {len(results) / elapsed:.1f} req/s")
    print(f"Успешных:     {ok}/{len(results)}")
    print(f"Статусы:      {dict(sorted(statuses.items()))}")
    if latencies:
        print(
            "Задержка, мс: "
            f"mean {statistics.fmean(latencies):.1f}, "
            f"p50 {percentile(latencies, 0.5):.1f}, "
            f"p90 {percentile(latencies, 0.9):.1f}, "
            f"p99 {percentile(latencies, 0.99):.1f}, "
            f"max {max(latencies):.1f}"
        )

    return 0 if ok == len(results) else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Нагрузочная проверка API MATCH")
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--method", default="GET")
    parser.add_argument("--path", default="/health")
    parser.add_argument("--token", default="")
    parser.add_argument("--body", default="")
    parser.add_argument("--requests", type=int, default=200)
    parser.add_argument("--concurrency", type=int, default=10)
    parser.add_argument("--timeout", type=float, default=30.0)
    args = parser.parse_args()
    if args.requests < 1 or args.concurrency < 1:
        parser.error("--requests и --concurrency должны быть >= 1")
    return asyncio.run(run(args))


if __name__ == "__main__":
    raise SystemExit(main())
