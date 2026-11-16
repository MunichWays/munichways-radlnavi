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
    elif site['status'] == 'inventory-open':
        text, css = 'Offen · noch ohne Geometrie', 'excluded'
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
    elif technical and technical.get('status') == 'draft-technical-check':
        attempted = [m for m in technical.get('movements', []) if m.get('kind') in ('left', 'straight')]
        passed = sum(m.get('enabled', False) for m in attempted)
        tech = f'Entwurf: {passed}/{len(attempted)} Links-/Geradeausbeziehungen offline bestanden; Sichtfreigabe und Aktivierung offen'
    elif technical:
        attempted = [m for m in technical.get('movements', []) if m.get('kind') in ('left', 'straight')]
        passed = sum(m.get('enabled', False) for m in attempted)
        tech = f'{passed}/{len(attempted)} Links-/Geradeausbeziehungen technisch bestanden'
        pending = sum(m.get('implementationPending', False) for m in technical.get('movements', []))
        if pending:
            tech += f'; {pending} Sonderfolgen noch nicht implementiert'
        sequences = sum(m.get('enabled', False) and m.get('requiresProtocolVersion') == 2 for m in technical.get('movements', []))
        if sequences:
            tech += f'; {sequences} Sonderfolgen implementiert/geprüft für neue App (v2)'
        templates = sum(bool(m.get('instructionTemplate')) and m.get('enabled', False) for m in technical.get('movements', []))
        if templates:
            tech += f'; {templates} Zweirichtungsradweg-Sonderansagen für neue App (v3)'
    elif matching and live:
        tech = f'{count} aktive Beziehungen im Live-Katalog'
    elif site['status'] == 'geometry-approved':
        tech = 'Technische Prüfung ausstehend'
    elif site['status'] == 'inventory-open':
        tech = 'Geometrie- und technische Prüfung ausstehend'
    elif site['status'] == 'geometry-draft':
        tech = 'Geometrie geändert; bisherige technische Prüfung gilt nicht für diese Revision'
    else:
        tech = 'Keine Aktivierung vorgesehen'
    return {'text': text, 'css': css, 'technical': tech, 'liveMovements': count, 'geometryMatches': matching}
