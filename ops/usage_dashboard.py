"""Generate the usage metrics and dashboard plan; apply with configure_usage.ps1."""
import json
from pathlib import Path

PROJECT = 'munichways-radlnavi-prod'
BASE = ('resource.type="cloud_run_revision" '
        f'AND logName="projects/{PROJECT}/logs/run.googleapis.com%2Frequests" '
        'AND httpRequest.requestMethod="GET" '
        'AND httpRequest.requestUrl=~"/route(/v1/|\\?)" ')
PROBES = ('(httpRequest.userAgent:"Google-Cloud-Scheduler" OR '
          'httpRequest.userAgent:"GoogleStackdriverMonitoring" OR '
          'httpRequest.userAgent:"RadlNavi-Route-Check")')


def plan():
    metrics = []
    for variant in ('standard', 'direct', 'discovery'):
        service = 'munichways-radlnavi-' + ('api' if variant == 'standard' else variant + '-api')
        variant_filter = BASE + f'AND resource.labels.service_name="{service}" '
        if variant == 'standard':
            variant_filter += 'AND NOT httpRequest.requestUrl=~"[?&]variant=(direct|discovery)(&|$)" '
        for kind, suffix in [('usage', 'AND NOT ' + PROBES), ('checks', 'AND ' + PROBES)]:
            name = f'radlnavi_routes_{variant}_{kind}'
            metrics.append({'name': name, 'description':
                f'{variant} route HTTP requests, {kind}; includes failures; excludes comfort/health. '
                'Usage includes manual tests and recalculations, not unique users. Starts at metric creation.',
                'filter': variant_filter + suffix,
                'metricDescriptor': {'metricKind': 'DELTA', 'valueType': 'INT64', 'unit': '1'}})

    def query(metric, service=None, full=False):
        f = f'resource.type="cloud_run_revision" AND metric.type="{metric}"'
        if service:
            f += f' AND resource.labels.service_name="{service}"'
        return {'timeSeriesFilter': {'filter': f, 'aggregation': {
            'alignmentPeriod': '86400s', 'perSeriesAligner': 'ALIGN_SUM',
            'crossSeriesReducer': 'REDUCE_SUM'}}, 'unitOverride': '1', 'outputFullDuration': full}

    widgets = [{'title': 'Nutzung richtig lesen', 'text': {'format': 'MARKDOWN', 'content':
        '**Zeitraum oben waehlen: letzte 30 Tage oder benutzerdefiniert der komplette Vormonat.** '
        'Summen gelten fuer den gewaehlten Zeitraum. Tagesbalken: 24-Stunden-Intervalle (UTC).\n\n'
        '**Routenzaehler starten am 07.11.2026** und schliessen Scheduler/Uptime-Pruefungen aus. '
        'Manuelle Tests, Wiederholungen, Navigation-Neuberechnungen und Fehler werden mitgezaehlt; keine Nutzerzahl. '
        'Standard zaehlt nur Standard-Routen am Standard-API-Eingang; Direct/Discovery werden jeweils an ihrer eigenen API gezaehlt.\n\n'
        '**Oktober 2026 ist fuer exakte Routenzahlen nicht mehr vollstaendig rekonstruierbar:** '
        'Request-Logs haben 30 Tage Aufbewahrung. Historische API-Gesamtaufrufe unten bleiben verfuegbar, '
        'enthalten aber auch Healthchecks, Komfortanalysen und Pruefungen. '
        'Leere Routendiagramme vor dem 07.11. bedeuten fehlende Messung, nicht null Nutzung.\n\n'
        '[Kostenbericht](https://console.cloud.google.com/billing?project=' + PROJECT + ') | '
        '[Betrieb und Ressourcen](https://console.cloud.google.com/monitoring/dashboards/builder/053c4dbf-5e35-40d8-b61d-9f3d26af3058?project=' + PROJECT + ')\n\n'
        'Instanzsekunden sind ein Kostenindikator, keine Euro-Abrechnung. Freikontingente, CPU/RAM, Starts und '
        'weitere Dienste beeinflussen die Rechnung; wenig Nutzung bedeutet nicht proportional wenig Kosten.'}}]
    for variant in ('standard', 'direct', 'discovery'):
        metric = 'logging.googleapis.com/user/radlnavi_routes_' + variant + '_usage'
        widgets.append({'title': variant.title() + ': Routenaufrufe im Zeitraum (ohne Pruefungen)',
                        'scorecard': {'timeSeriesQuery': query(metric, full=True)}})
        widgets.append({'title': variant.title() + ': Routenaufrufe pro Tag (ohne Pruefungen)',
                        'xyChart': {'dataSets': [{'timeSeriesQuery': query(metric), 'plotType': 'STACKED_BAR'}],
                                    'yAxis': {'label': 'Routenaufrufe', 'scale': 'LINEAR'}}})
    for kind, title in [('usage', 'Routenaufrufe nach Variante pro Tag'), ('checks', 'Automatische Routenpruefungen pro Tag')]:
        widgets.append({'title': title, 'xyChart': {'dataSets': [
            {'timeSeriesQuery': query('logging.googleapis.com/user/radlnavi_routes_' + v + '_' + kind),
             'legendTemplate': v.title(), 'plotType': 'STACKED_BAR'} for v in ('standard', 'direct', 'discovery')],
            'yAxis': {'scale': 'LINEAR'}}})
    for metric, title, unit in [('request_count', 'Standard-API: ALLE HTTP-Aufrufe', '1'),
                               ('container/billable_instance_time', 'Standard-API: abrechenbare Instanzsekunden', 's')]:
        for full in (True, False):
            q = query('run.googleapis.com/' + metric, 'munichways-radlnavi-api', full)
            q['unitOverride'] = unit
            widgets.append({'title': title + (' im Zeitraum' if full else ' pro Tag'),
                            **({'scorecard': {'timeSeriesQuery': q}} if full else
                               {'xyChart': {'dataSets': [{'timeSeriesQuery': q, 'plotType': 'STACKED_BAR'}]}})})
    for metric, title, unit in [('request_count', 'Alle Dienste: HTTP-Aufrufe pro Tag (inkl. interner Aufrufe)', '1'),
                               ('container/billable_instance_time', 'Alle Dienste: abrechenbare Instanzsekunden pro Tag', 's')]:
        q = query('run.googleapis.com/' + metric)
        q['timeSeriesFilter']['filter'] += ' AND resource.labels.service_name=starts_with("munichways-radlnavi-")'
        q['timeSeriesFilter']['aggregation']['groupByFields'] = ['resource.labels.service_name']
        q['unitOverride'] = unit
        widgets.append({'title': title, 'xyChart': {'dataSets': [
            {'timeSeriesQuery': q, 'plotType': 'STACKED_BAR', 'legendTemplate': '${resource.labels.service_name}'}]}})
    history_path = Path(__file__).with_name('usage-history.json')
    if history_path.exists():
        history = json.loads(history_path.read_text(encoding='utf-8-sig'))
        counts = history['counts']
        rows = ['| Tag (Europe/Berlin) | Standard | Direct | Discovery |', '|---|---:|---:|---:|']
        rows.extend(f"| {d['day']} | {d['counts']['standard']} | {d['counts']['direct']} | {d['counts']['discovery']} |"
                    for d in history['days'])
        widgets.insert(1, {'title': 'Letzte 30 Tage: historische Auswertung (Stand 07.11.2026)',
            'text': {'format': 'MARKDOWN', 'content':
                f"**Standard: {counts['standard']} · Direct: {counts['direct']} · Discovery: {counts['discovery']}**\n\n"
                f"Archivierter Stand: {history['start']} bis {history['end']} (UTC), 30 Tage. "
                'Ohne automatische Scheduler/Uptime-Pruefungen; inklusive manueller Tests und Fehler. '
                'Diese historische Tabelle ist eine Momentaufnahme. Die Diagramme darunter aktualisieren sich automatisch ab dem 07.11.2026. '
                'Erster und letzter Tag sind Teil-Tage; nicht aufgefuehrte Tage hatten keine passenden Requests.\n\n' + '\n'.join(rows)}})
    return {'metrics': metrics, 'dashboard': {'displayName': 'RadNavi - Nutzung und Routenaufrufe',
            'gridLayout': {'columns': '2', 'widgets': widgets}}}


if __name__ == '__main__':
    Path(__file__).with_name('usage-plan.json').write_text(json.dumps(plan(), indent=2) + '\n', encoding='utf-8')
    print('Usage plan written.')
