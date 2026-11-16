/** Route-only German preview, following Flutter VoiceGuidance's text rules.
 * GPS recovery, offset filtering and actual speech timing are not simulated.
 */
export type PreviewRow = {
  step: any; at: number; instruction: string; legIndex: number; stepIndex: number;
  detectedWayType?: 'road' | 'cycleway' | null;
  appInstruction?: string; appSpeech?: string; previewKey?: string; context?: string;
  appDisplay?: string;
};
const sentence = (text: string) => text.charAt(0).toUpperCase() + text.slice(1).replace(/[.!?]+$/, '') + '.';
const point = (p: any): boolean => Array.isArray(p) && p.length === 2 && p.every(Number.isFinite);
const finite = (n: any): boolean => typeof n === 'number' && Number.isFinite(n) && n >= 0;
const localized = (s: any): boolean => typeof s?.de === 'string' && !!s.de.trim() &&
  typeof s?.en === 'string' && !!s.en.trim();

function junctions(route: any): any[] {
  const guidance = route?.guidance;
  if (!['big-junctions-v1', 'big-junctions-v2', 'big-junctions-v3'].includes(guidance?.version) ||
      !Array.isArray(guidance?.junctions)) return [];
  const result: any[] = [];
  const ids = new Set<string>();
  for (const j of guidance.junctions) {
    const steps = route.legs?.[j?.legIndex]?.steps;
    if (!Array.isArray(steps) || !Number.isInteger(j.legIndex) || ids.has(j.occurrenceId) ||
        typeof j.occurrenceId !== 'string' || !['left', 'straight', 'uturn'].includes(j.movement) ||
        !finite(j.entry?.distanceAlongRouteMeters) || !finite(j.exit?.distanceAlongRouteMeters) ||
        j.entry.distanceAlongRouteMeters >= j.exit.distanceAlongRouteMeters ||
        !point(j.entry.location) || !point(j.exit.location) ||
        !Array.isArray(j.suppressedStepIndices) || j.suppressedStepIndices.some((i: any) =>
          !Number.isInteger(i) || i < 0 || i >= steps.length)) return [];
    if (j.instruction != null) {
      const i = j.instruction;
      const expected = j.movement === 'left' ? 'two-way-left-near' :
        j.movement === 'straight' ? 'two-way-straight-opposite' : undefined;
      if (guidance.version !== 'big-junctions-v3' || j.sequence || i.version !== 1 ||
          i.templateId !== expected || !expected || !localized(i.advance) || !localized(i.display) ||
          Object.keys(i.advance).sort().join(',') !== 'de,en' ||
          Object.keys(i.display).sort().join(',') !== 'de,en' ||
          Object.values(i.advance).some(t => typeof t !== 'string' || t.length > 240) ||
          Object.values(i.display).some(t => typeof t !== 'string' || t.length > 80)) return [];
    }
    if (j.sequence) {
      const s = j.sequence;
      if (!['big-junctions-v2', 'big-junctions-v3'].includes(guidance.version) || s.version !== 1 || !localized(s.advance) || !localized(s.display) ||
          !Array.isArray(s.checkpoints) || !s.checkpoints.length || s.checkpoints.length > 6) return [];
      let previous = j.entry.distanceAlongRouteMeters - 5;
      const checkpoints = new Set<string>();
      for (const cp of s.checkpoints) {
        if (typeof cp.id !== 'string' || checkpoints.has(cp.id) || !localized(cp.instruction) ||
            (cp.alignedInstruction && !localized(cp.alignedInstruction)) ||
            !point(cp.anchor?.location) || !finite(cp.anchor?.distanceAlongRouteMeters) ||
            cp.anchor.distanceAlongRouteMeters < previous + 5 ||
            cp.anchor.distanceAlongRouteMeters > j.exit.distanceAlongRouteMeters) return [];
        previous = cp.anchor.distanceAlongRouteMeters;
        checkpoints.add(cp.id);
      }
    } else if (j.movement === 'uturn') return [];
    if (result.some(other => other.entry.distanceAlongRouteMeters < j.exit.distanceAlongRouteMeters &&
        j.entry.distanceAlongRouteMeters < other.exit.distanceAlongRouteMeters)) return [];
    ids.add(j.occurrenceId);
    result.push(j);
  }
  return result;
}

const directions: Record<string, string> = {
  uturn: 'wenden', 'sharp right': 'scharf rechts abbiegen', 'slight right': 'leicht rechts halten',
  right: 'rechts abbiegen', 'sharp left': 'scharf links abbiegen',
  'slight left': 'leicht links halten', left: 'links abbiegen',
};
function wayType(step: any): 'road' | 'cycleway' | null {
  if (step.mode !== 'cycling') return null;
  const classes = step.intersections?.[0]?.classes || [];
  return classes.includes('road') === classes.includes('cycleway') ? null :
    classes.includes('road') ? 'road' : 'cycleway';
}
function action(row: PreviewRow, compact = false): string {
  const m = row.step.maneuver || {};
  const roundabout = ['roundabout', 'rotary', 'roundabout turn'].includes(m.type);
  let text = directions[m.modifier] || 'geradeaus weiterfahren';
  if (roundabout) {
    const ordinal = ['erste', 'zweite', 'dritte', 'vierte', 'fünfte', 'sechste'][m.exit - 1] || `${m.exit}.`;
    text = m.exit ? `im Kreisverkehr die ${ordinal} Ausfahrt nehmen` : 'in den Kreisverkehr einfahren';
  } else if (compact) {
    text = text.replace(' abbiegen', '').replace(' halten', '').replace(' weiterfahren', '');
  }
  const name = (row.step.name || '').trim().replace(/\s+/g, ' ');
  if (!compact && wayType(row.step) === 'road' && name) {
    return `${text}, ${name.toLowerCase().endsWith('platz') ? 'auf' : 'in'} ${name}`;
  }
  return text + (row.detectedWayType ? `, auf ${row.detectedWayType === 'road' ? 'Straße' : 'Radweg'}` : '');
}

/** Keep raw rows visible; add macro prompts and explicitly mark quiet steps. */
export function appGuidancePreview(route: any, raw: PreviewRow[]) {
  const approved = junctions(route);
  const suppressed = new Set<string>();
  approved.forEach(j => j.suppressedStepIndices.forEach((i: number) => suppressed.add(`${j.legIndex}-${i}`)));
  const relevant = (r: PreviewRow) => !suppressed.has(`${r.legIndex}-${r.stepIndex}`) &&
    !['depart', 'arrive'].includes(r.step.maneuver?.type) &&
    (r.detectedWayType || (r.step.maneuver?.type !== 'notification' &&
      !(r.step.maneuver?.type === 'new name' && (!r.step.maneuver.modifier || r.step.maneuver.modifier === 'straight'))));
  const maneuvers = raw.filter(relevant);
  const rows: PreviewRow[] = raw.map(row => {
    const type = row.step.maneuver?.type;
    let speech: string | undefined;
    let text: string;
    if (suppressed.has(`${row.legIndex}-${row.stepIndex}`)) {
      text = 'Keine Einzelansage – innerhalb der großen Kreuzung.';
    } else if (type === 'depart') {
      text = 'Startvorschau abhängig von Startposition und nächstem Manöver.';
    } else if (type === 'arrive') {
      speech = row.legIndex < (route.legs?.length || 1) - 1
        ? `Du hast das Zwischenziel ${row.legIndex + 1} erreicht.` : 'Du hast das Ziel erreicht.';
      text = speech;
    } else if (!relevant(row)) {
      text = 'Keine reguläre Abbiegeansage (gefiltertes Manöver).';
    } else {
      const next = maneuvers[maneuvers.indexOf(row) + 1];
      const close = next && next.at > row.at && next.at - row.at <= 35;
      speech = `Hier ${action(row, !!close)}${close ? `, danach sofort ${action(next, true)}` : ''}.`;
      text = `60 m / hier ${speech.slice('Hier '.length)}`;
    }
    return { ...row, appInstruction: text, appSpeech: speech };
  });
  let previousExit = 0;
  approved.sort((a, b) => a.entry.distanceAlongRouteMeters - b.entry.distanceAlongRouteMeters).forEach(j => {
    const advance = sentence(j.instruction?.advance.de || j.sequence?.advance.de || (j.movement === 'straight'
      ? 'an der großen Kreuzung geradeaus fahren' : 'an der großen Kreuzung links abbiegen'));
    const entry = j.entry.distanceAlongRouteMeters;
    const add = (key: string, at: number, location: number[], speech: string, context: string, alternative?: string, display?: string) => {
      rows.push({ at, step: { distance: 0, name: '', maneuver: { type: 'junction preview', location } },
        legIndex: j.legIndex, stepIndex: -1, previewKey: `${j.occurrenceId}-${key}`, instruction: '—',
        appSpeech: speech, appInstruction: alternative ? `${speech} Alternative Anfahrt: ${alternative}` : speech,
        context, appDisplay: display });
    };
    const firstAt = Math.max(previousExit, entry - 120);
    const display = j.instruction?.display.de || j.sequence?.display.de || `große Kreuzung ${j.movement === 'straight' ? 'geradeaus' : 'links'}`;
    add('advance', firstAt, j.entry.location, advance, '120/40 m vor Beginn der Kreuzung',
      undefined, `120/40 m ${display}`);
    j.sequence?.checkpoints.forEach((cp: any) => add(cp.id, cp.anchor.distanceAlongRouteMeters,
      cp.anchor.location, cp.instruction.de, 'Interner Sonderhinweis; geplant bis 12 m vor der Stelle, GPS-/richtungsabhängig',
      cp.alignedInstruction?.de));
    previousExit = j.exit.distanceAlongRouteMeters;
  });
  rows.sort((a, b) => a.at - b.at || Number(!!b.previewKey) - Number(!!a.previewKey));
  return { rows, junctionCount: approved.length,
    invalidMetadata: !!route?.guidance && approved.length === 0 && route.guidance.junctions?.length !== 0 };
}
