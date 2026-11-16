import { appGuidancePreview } from './appGuidancePreview';
import { listSteps } from './RouteInspector';
import wilram from './testFixtures/wilram-sequence.json';
import k19 from './testFixtures/k19-crossing.json';
import excluded from './testFixtures/k21-excluded.json';
import k24Left from './testFixtures/k24-west-north-left-entry-4-exit-6.json';
import k24Standard from './testFixtures/k24-west-north-left-entry-4-exit-1.json';
import k24Straight from './testFixtures/k24-north-south-straight-entry-1-exit-3.json';

test('K24 reverse-side templates use backend text while right-side left remains standard', () => {
  for (const data of [k24Left, k24Straight]) {
    const route: any = data.routes[0];
    const result = appGuidancePreview(route, listSteps(route));
    expect(result.junctionCount).toBe(1);
    const macro = result.rows.find(r => r.previewKey)!;
    expect(macro.appSpeech).toBe(route.guidance.junctions[0].instruction.advance.de);
    expect(macro.appDisplay).toBe('120/40 m '+route.guidance.junctions[0].instruction.display.de);
    expect(result.rows.filter(r => r.previewKey)).toHaveLength(1);
  }
  const standard: any = k24Standard.routes[0];
  const result = appGuidancePreview(standard, listSteps(standard));
  expect(result.rows.find(r => r.previewKey)!.appSpeech).toBe('An der großen Kreuzung links abbiegen.');
  const invalid = JSON.parse(JSON.stringify(k24Left.routes[0]));
  invalid.guidance.junctions[0].instruction.templateId = 'opposite-left';
  expect(appGuidancePreview(invalid, listSteps(invalid)).invalidMetadata).toBe(true);
});

test('real v1 crossing summarizes advance prompts and suppresses only reviewed steps', () => {
  const route: any = k19.routes[0];
  const original = JSON.stringify(route);
  const result = appGuidancePreview(route, listSteps(route));
  expect(result.junctionCount).toBe(1);
  const prompts = result.rows.filter(r => r.previewKey);
  expect(prompts).toHaveLength(1);
  expect(prompts[0].appSpeech).toBe('An der großen Kreuzung geradeaus fahren.');
  expect(prompts[0].appDisplay).toBe('120/40 m große Kreuzung geradeaus');
  expect(prompts[0].context).toContain('120/40 m');
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
  expect(prompts).toHaveLength(3);
  expect(prompts[0].appSpeech).toContain('danach sofort rechts');
  expect(prompts[1].appSpeech).toBe('Hier rechts.');
  expect(prompts[1].appInstruction).toContain('Alternative Anfahrt: Hier geradeaus.');
  expect(prompts[2].appSpeech).toBe('Hier links in Wilramstraße.');
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

test('long approach shows one summary at the first advance position', () => {
  const route: any = JSON.parse(JSON.stringify(k19.routes[0]));
  route.guidance.junctions[0].entry.distanceAlongRouteMeters = 200;
  route.guidance.junctions[0].exit.distanceAlongRouteMeters = 300;
  const result = appGuidancePreview(route, listSteps(route));
  expect(result.rows.filter(r => r.previewKey).map(r => r.at)).toEqual([80]);
});
