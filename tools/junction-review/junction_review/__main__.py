"""python -m junction_review: import, serve or export a local project."""
import argparse
import json
from pathlib import Path

from .adapters import export_review, import_radlnavi
from .model import summarize, validate_dataset
from .server import create_server
from .store import ProjectStore, atomic_write


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    legacy = commands.add_parser('import-radlnavi', help='Vorhandene Bildrunde importieren')
    legacy.add_argument('--source', type=Path, required=True)
    legacy.add_argument('--project', type=Path, required=True)
    legacy.add_argument('--id', default='junction-review')
    legacy.add_argument('--city', required=True)
    legacy.add_argument('--district', default='')
    legacy.add_argument('--area', type=Path, help='Optionales GeoJSON-Polygon; Auswahl nach Kreuzungsmittelpunkt')
    legacy.add_argument('--numbers', type=int, nargs='+')
    legacy.add_argument('--refresh', action='store_true')
    generic = commands.add_parser('import', help='Städteunabhängiges Projektformat importieren')
    generic.add_argument('--source', type=Path, required=True)
    generic.add_argument('--project', type=Path, required=True)
    generic.add_argument('--refresh', action='store_true')
    serve = commands.add_parser('serve')
    serve.add_argument('--project', type=Path, required=True)
    serve.add_argument('--port', type=int, default=8765)
    start = commands.add_parser('start', help='Gesamte migrierte Kreuzungsprüfung öffnen')
    start.add_argument('--project', type=Path, default=Path(__file__).resolve().parents[3] / '.local/junction-review/munich')
    start.add_argument('--port', type=int, default=8765)
    demo = commands.add_parser('demo', help='K47–K50 einmalig importieren und öffnen')
    demo.add_argument('--project', type=Path, default=Path(__file__).resolve().parents[3] / '.local/junction-review/munich-nine-lanes')
    demo.add_argument('--port', type=int, default=8765)
    export = commands.add_parser('export')
    export.add_argument('--project', type=Path, required=True)
    export.add_argument('--output', type=Path, required=True)
    status = commands.add_parser('status', help='Kompakter Stand für Mensch oder Agent')
    status.add_argument('--project', type=Path, required=True)
    status.add_argument('--json', action='store_true')
    migrate = commands.add_parser('migrate-overview', help='Vollständige bisherige RadlNavi-Übersicht übernehmen')
    migrate.add_argument('--repository', type=Path, default=Path(__file__).resolve().parents[3])
    migrate.add_argument('--project', type=Path, default=Path(__file__).resolve().parents[3] / '.local/junction-review/munich')
    migrate.add_argument('--id', default='munich')
    migrate.add_argument('--city', default='München')
    migrate.add_argument('--refresh', action='store_true')
    migrate.add_argument('--carry-project', type=Path, help='Lokale Entscheidungen aus einer bisherigen Teilmenge erhalten')
    technical = commands.add_parser('import-technical', help='Passenden technischen Prüfbericht zurück in die Karte übernehmen')
    technical.add_argument('--report', type=Path, required=True)
    technical.add_argument('--project', type=Path, default=Path(__file__).resolve().parents[3] / '.local/junction-review/munich')
    missing = commands.add_parser('prepare-open', help='Fehlende Geometrien offener Faelle regelbasiert vorbereiten')
    missing.add_argument('--project', type=Path, required=True)
    publish = commands.add_parser('publish-map', help='Oeffentlichen Nur-Lese-Kartenstand exportieren')
    publish.add_argument('--project', type=Path, required=True)
    publish.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    try:
        store = ProjectStore(args.project)
        if args.command == 'demo' and not (args.project / 'project.json').exists():
            source = Path(__file__).resolve().parents[3] / 'docs/large-junction-analysis/review-batch-09-nine-lanes-images/review-data.json'
            store.import_dataset(import_radlnavi(source, 'munich-nine-lanes', 'München', 'K47–K50 · Neun Fahrspuren'))
        if args.command == 'publish-map':
            from .publication import public_snapshot
            public = public_snapshot(store.snapshot())
            atomic_write(args.output, public)
            print(f'{len(public["sites"])} Kreuzungen fuer die oeffentliche Nur-Lese-Karte exportiert.')
        elif args.command == 'prepare-open':
            from .prepare_open import prepare_missing
            result = prepare_missing(args.project)
            print(', '.join(f'{key}: {len(value)}' for key, value in result.items() if isinstance(value, list)))
            print('Geometrien zur Sichtpruefung: ' + str(result['projectSummary']['readyForGeometryReview']))
        elif args.command == 'import-technical':
            print(f'{store.import_technical(json.loads(args.report.read_text(encoding="utf-8")))} technische Prüfergebnisse übernommen.')
        elif args.command == 'migrate-overview':
            from .radlnavi_overview import import_overview
            data = import_overview(args.repository, args.id, args.city)
            changed = store.import_dataset(data, args.refresh)
            if args.carry_project:
                print(f'{store.carry_edits(ProjectStore(args.carry_project))} lokale Bearbeitungen übernommen.')
            print(f"{len(data['sites'])} Fälle mit Freigaben und Live-Evidenz " + ('übernommen.' if changed else 'unverändert.'))
        elif args.command == 'import-radlnavi':
            area = json.loads(args.area.read_text(encoding='utf-8')) if args.area else None
            data = import_radlnavi(args.source, args.id, args.city, args.district, area, args.numbers)
            changed = store.import_dataset(data, args.refresh)
            print(f"{len(data['sites'])} Kreuzungen; " + ('importiert.' if changed else 'unverändert.'))
        elif args.command == 'import':
            data = json.loads(args.source.read_text(encoding='utf-8'))
            validate_dataset(data)
            changed = store.import_dataset(data, args.refresh)
            print('Importiert.' if changed else 'Unverändert.')
        elif args.command == 'status':
            report = summarize(store.snapshot())
            if args.json:
                print(json.dumps(report, ensure_ascii=False, indent=2))
            else:
                print(f"{report['project']['city']}: {report['total']} Kreuzungen; " + ', '.join(f'{key}: {value}' for key, value in report['counts'].items()))
                for site in report['sites']:
                    flags = ('; alte Entscheidung ungültig' if site['staleDecision'] else '')
                    if site['unassignedGates']:
                        flags += '; Straßenarme offen: ' + ', '.join(site['unassignedGates'])
                    label = f"K{site['number']}" if site['number'] else site['id']
                    print(f"{label} v{site['geometryRevision']}: {site['status']}{flags}")
        elif args.command == 'export':
            result = export_review(store.snapshot())
            atomic_write(args.output, result)
            print(f"{len(result['sites'])} bestätigte Geometrien exportiert; technische Prüfung erforderlich.")
        else:
            store.snapshot()
            server = create_server(store, args.port)
            print(f'Kreuzungsprüfung: http://127.0.0.1:{server.server_port}', flush=True)
            print('Beenden mit Strg+C. Entscheidungen werden im Projekt gespeichert.', flush=True)
            try:
                server.serve_forever()
            except KeyboardInterrupt:
                pass
            finally:
                server.server_close()
    except (ValueError, OSError, KeyError, TypeError) as error:
        parser.exit(1, str(error) + '\n')


if __name__ == '__main__':
    main()
