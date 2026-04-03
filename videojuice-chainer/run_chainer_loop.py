import datetime
import json
import os
import sys
import time
from pathlib import Path

import requests


def parse_int(env_name: str, default_value: int) -> int:
    value = os.getenv(env_name, "").strip()
    if value == "":
        return default_value
    try:
        return int(value)
    except ValueError:
        return default_value


def get_env_url(primary_name: str, fallback_name: str) -> str:
    primary = os.getenv(primary_name, "").strip()
    if primary:
        return primary
    return os.getenv(fallback_name, "").strip()


def ensure_log_dir() -> Path:
    log_dir = Path(os.getenv("LOG_DIR", "logs"))
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir


def open_log_file(log_dir: Path) -> Path:
    ts = datetime.datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    return log_dir / f"videojuice-chainer-{ts}.log"


def build_headers() -> dict:
    platform_secret = os.getenv("PLATFORM_SECRET", "").strip()
    if not platform_secret:
        raise ValueError("PLATFORM_SECRET is required.")

    platform_user = os.getenv("PLATFORM_USER", "").strip() or "github-actions-chainer"
    return {
        "User-Agent": "videojuice-chainer/1.0 (+github-actions)",
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/json",
        "x-platform-password": platform_secret,
        "x-platform-user": platform_user,
    }


def send_chainer_request(session: requests.Session, url: str, headers: dict, timeout_seconds: int) -> dict:
    start = time.perf_counter()
    try:
        response = session.post(
            url,
            headers=headers,
            json={"action": "run_chainer"},
            timeout=timeout_seconds,
        )
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        text = response.text or ""
        if len(text) > 1000:
            text = text[:1000] + "... [truncated]"
        return {
            "ok": response.ok,
            "status": response.status_code,
            "elapsed_ms": elapsed_ms,
            "body": text,
        }
    except Exception as error:
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        return {
            "ok": False,
            "status": None,
            "elapsed_ms": elapsed_ms,
            "error": str(error),
        }


def main() -> int:
    chainer_url = get_env_url("CHAINER_URL", "CHAINER_URL_SECRET")
    if not chainer_url:
        print("ERROR: CHAINER_URL (or CHAINER_URL_SECRET) is required.", file=sys.stderr)
        return 2

    interval_seconds = max(parse_int("INTERVAL_SECONDS", 20), 1)
    duration_seconds = parse_int("DURATION_SECONDS", 290)
    timeout_seconds = max(parse_int("TIMEOUT_SECONDS", 20), 1)

    try:
        headers = build_headers()
    except ValueError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2

    log_dir = ensure_log_dir()
    log_path = open_log_file(log_dir)

    start_time = time.time()
    end_time = start_time + max(duration_seconds, 0)
    attempts = 0
    successes = 0
    failures = 0

    with requests.Session() as session:
        with log_path.open("a", encoding="utf-8") as fh:
            def log(line: str):
                fh.write(line + "\n")
                fh.flush()
                print(line)

            log(
                f"[start] utc={datetime.datetime.utcnow().isoformat()} "
                f"url={chainer_url} interval={interval_seconds}s duration={duration_seconds}s timeout={timeout_seconds}s"
            )

            mode = "single" if duration_seconds <= 0 else "loop"

            try:
                while True:
                    now = time.time()
                    if mode == "loop" and now >= end_time:
                        break

                    attempts += 1
                    ts = datetime.datetime.utcnow().isoformat()
                    result = send_chainer_request(session, chainer_url, headers, timeout_seconds)

                    if result["ok"]:
                        successes += 1
                        log(
                            f"[{ts}] status={result['status']} elapsed_ms={result['elapsed_ms']} "
                            f"body={json.dumps(result['body'])}"
                        )
                    else:
                        failures += 1
                        error_message = result.get("error") or result.get("body") or "Unknown error"
                        log(
                            f"[{ts}] error status={json.dumps(result['status'])} elapsed_ms={result['elapsed_ms']} "
                            f"err={json.dumps(error_message)}"
                        )

                    if mode == "single":
                        break

                    remaining = interval_seconds
                    while remaining > 0:
                        if time.time() + remaining > end_time and mode == "loop":
                            remaining = max(0, int(end_time - time.time()))
                        if remaining <= 0:
                            break
                        time.sleep(min(1, remaining))
                        remaining -= 1
            except KeyboardInterrupt:
                log("[interrupt] Received KeyboardInterrupt; exiting loop.")

            summary = {
                "attempts": attempts,
                "successes": successes,
                "failures": failures,
                "utc_end": datetime.datetime.utcnow().isoformat(),
                "log_path": str(log_path),
            }
            log("[summary] " + json.dumps(summary))

    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
