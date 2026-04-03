# VideoJuice GitHub Chainer

This folder contains the GitHub Actions runner that repeatedly calls `apiJobChainerHandler` for a few minutes at a time.

Why it exists:

- Google Cloud Scheduler cannot run faster than once per minute.
- GitHub Actions cannot natively schedule faster than every 5 minutes.
- The workflow works around that by starting on a normal GitHub schedule and then looping every few seconds inside a single job run.

Required GitHub secrets:

- `VIDEOJUICE_CHAINER_URL`
- `VIDEOJUICE_PLATFORM_SECRET`

Optional workflow inputs:

- `chainer_url`
- `platform_user`
- `interval_seconds`
- `duration_seconds`

Recommended defaults:

- `interval_seconds=20`
- `duration_seconds=290`

This keeps one workflow run active for almost the full 5-minute window, so the next scheduled run can pick up where the previous one ended.

Limitations:

- GitHub scheduled workflows are best-effort and can start late.
- If you need hard real-time or guaranteed sub-minute cadence, use an always-on worker instead of GitHub Actions.
