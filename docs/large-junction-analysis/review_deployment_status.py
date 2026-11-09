"""Keep human geometry approval, technical evidence and actual deployment separate."""


def status_for(site, state, technical=None):
    if technical and technical.get('geometryRevision') != site['version']:
        technical = None
    live = next((j for j in state.get('junctions', []) if j['id'] == site['id'] and j.get('enabled')), None)
    count = sum(m.get('enabled', False) for m in live['movements']) if live else 0
    matching = bool(live and live['polygon']['coordinates'][0] == site['polygon'])
    if live and matching:
        text, css = f'LIVE · v{site["version"]} · {count} Fahrbeziehungen', 'live'
    elif live:
        text, css = f'LIVE: ältere Fläche · {count} Fahrbeziehungen; v{site["version"]} noch nicht deployed', 'older'
    elif site['status'] == 'permanently-excluded':
        text, css = 'Ausgeschlossen · nicht deployed', 'excluded'
    elif site['status'] == 'excluded':
        text, css = 'Ausgeschlossen · nicht deployed', 'excluded'
    elif site['status'] == 'geometry-draft':
        text, css = 'Korrigierter Entwurf · nicht deployed', 'pending'
    elif site['status'] != 'geometry-approved':
        text, css = 'Zurückgestellt · nicht deployed', 'pending'
    else:
        text, css = 'NICHT DEPLOYED', 'pending'
    if not state:
        text, css = 'Live-Stand noch nicht abgeglichen', 'pending'
    if technical and technical.get('status') == 'in_progress':
        tech = 'Technische Prüfung läuft'
    elif technical:
        attempted = [m for m in technical.get('movements', []) if m.get('kind') != 'right']
        passed = sum(m.get('enabled', False) for m in attempted)
        tech = f'{passed}/{len(attempted)} Links-/Geradeausbeziehungen technisch bestanden'
    elif matching and live:
        tech = f'{count} aktive Beziehungen im Live-Katalog'
    elif site['status'] == 'geometry-approved':
        tech = 'Technische Prüfung ausstehend'
    elif site['status'] == 'geometry-draft':
        tech = 'Geometrie geändert; bisherige technische Prüfung gilt nicht für diese Revision'
    else:
        tech = 'Keine Aktivierung vorgesehen'
    return {'text': text, 'css': css, 'technical': tech, 'liveMovements': count, 'geometryMatches': matching}
