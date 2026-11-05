# RadNavi Monitoring

Configured on 2026-11-04 in `munichways-radlnavi-prod`.

- Dashboard: https://console.cloud.google.com/monitoring/dashboards/builder/053c4dbf-5e35-40d8-b61d-9f3d26af3058?project=munichways-radlnavi-prod
- Charts for all seven Cloud Run services: traffic, 5xx, latency p95, memory p95,
  CPU p95, instances, startup latency and billable instance time.
- Added alerts: memory >85% for 10 minutes, CPU >85% for 15 minutes,
  request latency p95 >10 seconds for 10 minutes, >5 HTTP 5xx per service in 5 minutes.
- New alerts and three existing availability/API policies notify
  `thomas.haeusler@munichways.de`. Existing checks are preserved.
- Budget requested: EUR 20/calendar month, project only; thresholds 50%, 80%,
  100% actual and 100% forecast. NOT CREATED: Budget API list/create returns HTTP 403.
  An administrator with billing.budgets permissions must configure it.
  Budget notifications are not a spending cap.

Reproduce: `python ops/configure_monitoring.py` writes the JSON plan without cloud
changes. `python ops/configure_monitoring.py --apply` uses the current gcloud login
and creates/updates the named dashboard and four new policies. It does not manage
the three legacy policies, billing budgets or Cloud Run resource limits.

## Findings and next actions

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
