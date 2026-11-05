"""Create/update RadNavi monitoring using the active gcloud login.

Run with --apply to change Cloud Monitoring; default only writes the JSON plan.
No service resource limits or billing settings are changed.
"""
import argparse
import json
import subprocess
import urllib.error
import urllib.request
from pathlib import Path

PROJECT = "munichways-radlnavi-prod"
ROOT = f"projects/{PROJECT}"
FILTER = 'resource.type="cloud_run_revision" AND resource.labels.service_name=starts_with("munichways-radlnavi-")'


def aggregation(aligner, reducer="REDUCE_MAX"):
    return {"alignmentPeriod": "300s", "perSeriesAligner": aligner,
            "crossSeriesReducer": reducer,
            "groupByFields": ["resource.labels.service_name"]}


def query(metric, aligner, reducer="REDUCE_MAX", extra=""):
    return {"filter": f'{FILTER} AND metric.type="run.googleapis.com/{metric}"{extra}',
            "aggregation": aggregation(aligner, reducer)}


def plan():
    widgets = [{"title": "RadNavi Betrieb und Kosten", "text": {
        "format": "MARKDOWN", "content":
        "[Kostenbericht](https://console.cloud.google.com/billing?project=" + PROJECT + ") | "
        "[Fehlerlogs](https://console.cloud.google.com/logs/query?project=" + PROJECT + ") | "
        "[Alarme](https://console.cloud.google.com/monitoring/alerting?project=" + PROJECT + ")\n\n"
        "Kostenindikatoren sind keine Euro-Abrechnung. Echte Kosten und Budgets stehen in Cloud Billing. "
        "Speicher/CPU: Maximum pro Dienst; Latenz: hoechster Revisions-p95. "
        "Scale-to-zero kann Messluecken verursachen. Bestehende Uptime-Pruefungen bleiben aktiv."}}]
    specs = [
        ("Anfragen / Sekunde", "request_count", "ALIGN_RATE", "REDUCE_SUM", "", "1/s"),
        ("HTTP 5xx / 5 Minuten", "request_count", "ALIGN_SUM", "REDUCE_SUM", ' AND metric.labels.response_code_class="5xx"', "1"),
        ("Antwortzeit p95 (ms)", "request_latencies", "ALIGN_PERCENTILE_95", "REDUCE_MAX", "", "ms"),
        ("Speicherauslastung p95", "container/memory/utilizations", "ALIGN_PERCENTILE_95", "REDUCE_MAX", "", "10^2.%"),
        ("CPU-Auslastung p95", "container/cpu/utilizations", "ALIGN_PERCENTILE_95", "REDUCE_MAX", "", "10^2.%"),
        ("Instanzen", "container/instance_count", "ALIGN_MAX", "REDUCE_SUM", "", "1"),
        ("Kaltstart p95 (ms)", "container/startup_latencies", "ALIGN_PERCENTILE_95", "REDUCE_MAX", "", "ms"),
        ("Abrechenbare Instanzsekunden / 5 Minuten", "container/billable_instance_time", "ALIGN_SUM", "REDUCE_SUM", "", "s"),
    ]
    for title, metric, aligner, reducer, extra, unit in specs:
        widgets.append({"title": title, "xyChart": {"dataSets": [{
            "timeSeriesQuery": {"timeSeriesFilter": query(metric, aligner, reducer, extra), "unitOverride": unit},
            "plotType": "LINE"}], "timeshiftDuration": "0s", "yAxis": {"scale": "LINEAR"}}})
    dashboard = {"displayName": "RadNavi - Betrieb und Ressourcen", "gridLayout": {"columns": "2", "widgets": widgets}}
    policies = []
    for title, metric, aligner, threshold, duration, extra, reducer in [
        ("RadNavi - Speicher ueber 85 Prozent", "container/memory/utilizations", "ALIGN_PERCENTILE_95", .85, "600s", "", "REDUCE_MAX"),
        ("RadNavi - CPU ueber 85 Prozent", "container/cpu/utilizations", "ALIGN_PERCENTILE_95", .85, "900s", "", "REDUCE_MAX"),
        ("RadNavi - Antwortzeit p95 ueber 10 Sekunden", "request_latencies", "ALIGN_PERCENTILE_95", 10000, "600s", "", "REDUCE_MAX"),
        ("RadNavi - Serverfehler alle Dienste", "request_count", "ALIGN_SUM", 5, "0s", ' AND metric.labels.response_code_class="5xx"', "REDUCE_SUM"),
    ]:
        q = query(metric, aligner, reducer, extra)
        policies.append({"displayName": title, "combiner": "OR", "enabled": True,
            "conditions": [{"displayName": title, "conditionThreshold": {
                "filter": q["filter"], "aggregations": [q["aggregation"]],
                "comparison": "COMPARISON_GT", "thresholdValue": threshold,
                "duration": duration, "trigger": {"count": 1}}}],
            "alertStrategy": {"autoClose": "1800s"},
            "documentation": {"mimeType": "text/markdown", "content":
                "Betroffenen Dienst und Revision im Monitoring pruefen, dann Fehlerlogs und Traffic vergleichen. "
                "Bei Speicherproblemen nach 'Memory limit' suchen. Vor Ressourcenanpassung Parallelitaet und Kosten pruefen. "
                "Keine automatische Skalierungs- oder Speicheranpassung."}})
    return dashboard, policies


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--email", default="thomas.haeusler@munichways.de")
    args = parser.parse_args()
    dashboard, policies = plan()
    Path(__file__).with_name("monitoring-plan.json").write_text(
        json.dumps({"dashboard": dashboard, "policies": policies}, indent=2) + "\n", encoding="utf-8")
    if not args.apply:
        print("Plan written; use --apply to configure Cloud Monitoring.")
        return
    token = subprocess.check_output(["gcloud.cmd", "auth", "print-access-token"], text=True).strip()

    def api(version, path, body=None, method=None):
        req = urllib.request.Request(f"https://monitoring.googleapis.com/{version}/{path}",
            data=json.dumps(body).encode() if body is not None else None,
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"}, method=method)
        try:
            with urllib.request.urlopen(req, timeout=60) as response:
                return json.load(response)
        except urllib.error.HTTPError as error:
            raise RuntimeError(error.read().decode()) from error

    channels = api("v3", f"{ROOT}/notificationChannels").get("notificationChannels", [])
    channels = [c["name"] for c in channels if c.get("enabled") and c.get("labels", {}).get("email_address") == args.email]
    if not channels:
        channel = api("v3", f"{ROOT}/notificationChannels", {
            "type": "email", "displayName": "RadNavi Betrieb", "enabled": True,
            "labels": {"email_address": args.email}}, "POST")
        channels = [channel["name"]]
    if len(channels) != 1:
        raise RuntimeError("Expected one enabled notification channel for the selected email")
    existing = api("v1", f"{ROOT}/dashboards").get("dashboards", [])
    match = [d for d in existing if d["displayName"] == dashboard["displayName"]]
    if len(match) > 1:
        raise RuntimeError("Duplicate dashboard names")
    if match:
        old = api("v1", match[0]["name"])
        dashboard.update(name=old["name"], etag=old["etag"])
    result = api("v1", dashboard.get("name", f"{ROOT}/dashboards"), dashboard, "PATCH" if match else "POST")
    print("Dashboard:", result["name"])
    dashboard_name = result["name"]
    existing = api("v3", f"{ROOT}/alertPolicies").get("alertPolicies", [])
    for policy in policies:
        policy["notificationChannels"] = channels
        match = [p for p in existing if p["displayName"] == policy["displayName"]]
        if len(match) > 1:
            raise RuntimeError("Duplicate policy names")
        if match:
            policy["name"] = match[0]["name"]
        result = api("v3", policy.get("name", f"{ROOT}/alertPolicies"), policy, "PATCH" if match else "POST")
        verified = api("v3", result["name"])
        if verified.get("validity"):
            raise RuntimeError(str(verified["validity"]))
        print("Verified:", verified["displayName"], verified["name"])
    api("v1", dashboard_name)


if __name__ == "__main__":
    main()
