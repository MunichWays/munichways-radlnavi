# RadNavi Monitoring

## Usage dashboard

Created on 2026-11-07:
https://console.cloud.google.com/monitoring/dashboards/builder/df525273-f176-435f-8e81-02e80c5af954?project=munichways-radlnavi-prod

Select the last 30 days or a custom full calendar month in the dashboard time
picker. Standard route count and daily chart appear first, followed by Direct
and Discovery, automatic probes, historical total Standard API requests, and
billable Standard API instance time. These last two metrics are cost indicators,
not a bill. Route counters begin on 2026-11-07 and persist beyond log retention.
They count GET requests to `/route/v1/...` or `/route?...`, including failures,
manual tests and recalculations. They are not unique users or journeys.
Standard excludes explicitly forwarded Direct/Discovery variants; those are
counted at their respective variant APIs. Scheduler and legacy uptime checker
user agents are excluded from usage and counted separately. Health and comfort
analysis endpoints are not routes. Daily metric alignment uses 24-hour UTC bins.

The dashboard also includes a dated historical 30-day snapshot from retained
request logs, grouped by Europe/Berlin day. This snapshot does not auto-refresh;
live metric charts below it do. `usage-history.json` contains only aggregates,
not request URLs, IPs or coordinates. Request log retention is 30 days; earliest
retained route log inspected on 2026-11-07 was 2026-10-08. Consequently, exact
full-October route counts cannot be reconstructed from the retained logs.
The first fully measured calendar month will be December 2026.

Reproduce: `./ops/configure_usage.ps1` generates/previews the six counter metrics
and dashboard; `-Apply` writes only those metrics and this usage dashboard.
`./ops/snapshot_usage.ps1` refreshes the historical aggregate snapshot; then
reapply the dashboard. It does not enable any recurring export or computation.
No application deployment, extra probes or minimum instances are needed.
The dashboard is under Monitoring > Dashboards rather than a modification of
the fixed Monitoring landing page.

Configured on 2026-11-04 in `munichways-radlnavi-prod`.

- Dashboard: https://console.cloud.google.com/monitoring/dashboards/builder/053c4dbf-5e35-40d8-b61d-9f3d26af3058?project=munichways-radlnavi-prod
- Charts for all seven Cloud Run services: traffic, 5xx, latency p95, memory p95,
  CPU p95, instances, startup latency and billable instance time.
- Added alerts: memory >85% for 10 minutes, CPU >85% for 15 minutes,
  request latency p95 >10 seconds for 10 minutes (>30 seconds for Direct/Discovery
  APIs since 2026-11-07), >5 HTTP 5xx per service in 5 minutes.
- Alerts notify `thomas.haeusler@munichways.de`. The two legacy uptime checks
  were replaced by daytime Scheduler route checks on 2026-11-07 (see below).
- Budget requested: EUR 20/calendar month, project only; thresholds 50%, 80%,
  100% actual and 100% forecast. NOT CREATED: Budget API list/create returns HTTP 403.
  An administrator with billing.budgets permissions must configure it.
  Budget notifications are not a spending cap.

Reproduce: `python ops/configure_monitoring.py` writes the JSON plan without cloud
changes. `python ops/configure_monitoring.py --apply` uses the current gcloud login
and creates/updates the named dashboard and four new policies. It does not manage
the three legacy policies, billing budgets or Cloud Run resource limits.

## Findings and next actions

On 2026-11-07, updated existing latency policy `2737926620328278465` in place:
Direct/Discovery APIs use >30 seconds; all other services retain >10 seconds.
Both conditions retain the 5-minute p95 alignment and 10-minute duration.
Read-back verified the conditions and preserved notification channel.
No minimum-instance changes were made.

Previously, uptime checks called the standard API `/health` every 300 seconds and
a standard OSRM route every 900 seconds. On 2026-11-07 these were replaced with
three Scheduler HTTP jobs (`radlnavi-route-check-standard`, `-direct`, `-discovery`):
each requests a short route every five minutes from 05:00 through 23:55,
Europe/Berlin (`*/5 5-23 * * *`). Route calls exercise both API and private router;
no separate health call or comfort analysis is needed. Idle retention is best
effort, not a guarantee. Five minutes also provides quicker failure detection
than ten; it is not a documented minimum idle retention time.

Reproduce with `./ops/configure_route_checks.ps1` (preview) or `-Apply`.
The helper verifies actual route content during setup and creates a log-based
email alert for Scheduler errors before removing the two legacy uptime alerts
and deleting their checks. Recurring checks validate HTTP success, not route JSON.
No retries are configured; the next regular attempt is five minutes later.
Setup route payloads were valid for all variants; Scheduler executions returned
HTTP 200. The replacement alert was read back successfully. Actual alert email
delivery has not been tested.
There are no active route probes from 00:00 through 04:59; user traffic still works.
App code loads alternatives concurrently only after the selected route is usable;
each variant has separate API/router instances.

Last seven days inspected on 2026-11-04: main API exceeded its 1 GiB memory limit
on October 29 and 31. Peak hourly memory p95 was 99.95%. A direct API request
returned 504 on October 30. Other service memory peaks: direct API 55.9%,
discovery API 44.0%, routing variants about 70.9%, frontend 18.8%.
CPU hourly p95 peaks were below 28% for all services.

Investigate main API memory retention and concurrent request load before choosing
between lower concurrency or a memory increase. Changes must also be reflected
in deployment definitions. Root cloudbuild.yaml has been corrected from 512Mi
to 1Gi, matching cloudbuild-api.yaml and production. No live resource changes made here.
Historical maxima do not establish that a leak still exists in the latest revision.

Verification: live API accepted dashboard and four policies; each policy was read
back with no validity error. Dashboard was read back. Notification-channel changes
on legacy policies were confirmed by API responses. Delivery of an actual alarm
email has not been tested.
