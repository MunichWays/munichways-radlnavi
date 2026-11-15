import { appGuidancePreview } from './appGuidancePreview';
import { listSteps } from './RouteInspector';
import wilram from './testFixtures/wilram-sequence.json';
import k19 from './testFixtures/k19-crossing.json';
import excluded from './testFixtures/k21-excluded.json';

test('real v1 crossing supplies both advance prompts and suppresses only reviewed steps', () => {
  const route: any = k19.routes[0];
  const original = JSON.stringify(route);
  const result = appGuidancePreview(route, listSteps(route));
  expect(result.junctionCount).toBe(1);
  const prompts = result.rows.filter(r => r.previewKey);
  expect(prompts).toHaveLength(2);
  expect(prompts[0].appSpeech).toBe('An der großen Kreuzung geradeaus fahren.');
  expect(prompts[1].appSpeech).toBe(prompts[0].appSpeech);
  expect(prompts[1].context).toContain('40 m');
  const j = route.guidance.junctions[0];
  j.suppressedStepIndices.forEach((i: number) => {
    const row = result.rows.find(r => r.legIndex === j.legIndex && r.stepIndex === i)!;
    expect(row.appSpeech).toBeUndefined();
    expect(row.appInstruction).toContain('Keine Einzelansage');
    expect(row.step).toBe(route.legs[j.legIndex].steps[i]);
  });
  expect(JSON.stringify(route)).toBe(original);
});

test('real Wilram sequence includes planned internal turns and the alternative approach', () => {
  const route: any = wilram.routes[0];
  const result = appGuidancePreview(route, listSteps(route));
  const prompts = result.rows.filter(r => r.previewKey);
  expect(prompts).toHaveLength(4);
  expect(prompts[0].appSpeech).toContain('danach sofort rechts');
  expect(prompts[2].appSpeech).toBe('Hier rechts.');
  expect(prompts[2].appInstruction).toContain('Alternative Anfahrt: Hier geradeaus.');
  expect(prompts[3].appSpeech).toBe('Hier links in Wilramstraße.');
  expect(prompts.every(r => r.step.maneuver.location.length === 2)).toBe(true);
});

test('excluded K21 relationship retains ordinary app and raw directions, without a macro', () => {
  const route: any = excluded.routes[0];
  const result = appGuidancePreview(route, listSteps(route));
  expect(result.junctionCount).toBe(0);
  expect(result.rows.some(r => r.previewKey)).toBe(false);
  expect(result.rows.some(r => r.appSpeech?.startsWith('Hier '))).toBe(true);
  expect(result.rows.some(r => r.appInstruction?.includes('innerhalb'))).toBe(false);
});

test.each(['version', 'steps', 'sequence'])('invalid %s metadata falls back without hiding raw steps', corruption => {
  const route: any = JSON.parse(JSON.stringify(wilram.routes[0]));
  if (corruption === 'version') route.guidance.version = 'future-version';
  if (corruption === 'steps') route.guidance.junctions[0].suppressedStepIndices = [999999];
  if (corruption === 'sequence') delete route.guidance.junctions[0].sequence.advance.en;
  const raw = listSteps(route);
  const result = appGuidancePreview(route, raw);
  expect(result.invalidMetadata).toBe(true);
  expect(result.rows).toHaveLength(raw.length);
  expect(result.rows.some(r => r.appInstruction?.includes('innerhalb'))).toBe(false);
});

test('long approach places the two prompts at entry minus 120 and 40 metres', () => {
  const route: any = JSON.parse(JSON.stringify(k19.routes[0]));
  route.guidance.junctions[0].entry.distanceAlongRouteMeters = 200;
  route.guidance.junctions[0].exit.distanceAlongRouteMeters = 300;
  const result = appGuidancePreview(route, listSteps(route));
  expect(result.rows.filter(r => r.previewKey).map(r => r.at)).toEqual([80, 160]);
});
