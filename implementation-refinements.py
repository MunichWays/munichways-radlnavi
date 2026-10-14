from pathlib import Path

root = Path('C:/Users/Thomas/dev/flutter/munich-ways-app')

p = root / 'lib/model/route_transfer.dart'
s = p.read_text(encoding='utf-8')
s = s.replace('  bool get hasNavigation => native != null;', r'''  bool get hasNavigation => native != null;

  static String gpxFilename(String name) {
    final clean = name.trim()
        .replaceAll(RegExp(r'[<>:"/\\|?*\x00-\x1f]'), '_')
        .replaceAll(RegExp(r'[. ]+$'), '')
        .replaceAll(RegExp(r'\.gpx$', caseSensitive: false), '')
        .replaceAll(RegExp(r'[. ]+$'), '');
    final reserved = RegExp(r'^(con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\.|$)',
        caseSensitive: false).hasMatch(clean);
    return '${clean.isEmpty || reserved ? 'MunichWays-Route' : clean}.gpx';
  }
''')
p.write_text(s, encoding='utf-8')
p = root / 'lib/api/route_transfer_io.dart'
s = p.read_text(encoding='utf-8').replace("fileNameOverrides: ['munichways-route.gpx']", 'fileNameOverrides: [RouteTransfer.gpxFilename(transfer.name)]')
p.write_text(s, encoding='utf-8')
p = root / 'lib/ui/map/map_screen_model.dart'
s = p.read_text(encoding='utf-8').replace('''    if (_originalRoute) {
      _displayErrorMsg(
          'Originalstrecke bleibt erhalten. Im Routenplaner bewusst neu planen.');
      return Future.value(false);
    }
    if (destination == null)''', '''    // Manual refresh deliberately leaves original-route mode. The stored
    // snapshot remains immutable and can still be opened again.
    _originalRoute = false;
    if (destination == null)''')
p.write_text(s, encoding='utf-8')
p = root / 'lib/ui/map/route_planner_sheet.dart'
s = p.read_text(encoding='utf-8')
s = s.replace('''  final initialStopCount = (initialPlan?.stops ?? model.waypoints).length;
  final initialChildSize =
      initialStopCount >= 1 || model.hasRouteComparison ? 1.0 : 0.55;
''', '')
s = s.replace('initialChildSize: initialChildSize', 'initialChildSize: 1.0').replace('0.55', '0.7')
start = s.index('                  Wrap(spacing: 8, children: [')
end = s.index('                  if (widget.model.isOriginalRoute)', start)
actions = s[start:end]
s = s[:start] + s[end:]
insert = s.index('          Expanded(\n              child: SingleChildScrollView(')
s = s[:insert] + actions + s[insert:]
p.write_text(s, encoding='utf-8')
p = root / 'test/ui/map/imported_route_test.dart'
s = p.read_text(encoding='utf-8').replace('import stays exact and survives refresh, settings and unchanged saved-route loading', 'import stays exact until deliberate refresh or editing')
s = s.replace('''    final original = model.route.route;
    expect(await model.refreshRoute(), false);
    expect(identical(model.route.route, original), true);
''', '')
insert = s.index("  test('late lazy snapshot load")
s = s[:insert] + '''  test('manual refresh recalculates and can recover without changing saved snapshot', () async {
    final transfer = RouteTransfer.fromJson(jsonDecode(
        File('test_resources/routing/route-transfer.json').readAsStringSync()));
    final provider = _Provider();
    final model = MapScreenViewModel(store: _Settings(),
        routingService: RoutingService(radlNavi: provider, bRouter: provider,
            radlNaviCoverage: OberbayernCoverage()));
    addTearDown(model.dispose);
    final saved = SavedRoute(name: transfer.name, start: transfer.plan.first,
        stops: transfer.plan.sublist(1, 3), destination: transfer.plan.last,
        snapshot: transfer);
    model.setSavedRoutePlan(saved);
    final refreshed = model.refreshRoute();
    await Future<void>.delayed(Duration.zero);
    expect(model.isOriginalRoute, false);
    expect(model.route.state, MapRouteState.LOADING);
    provider.ready.completeError(Exception('temporary failure'));
    expect(await refreshed, false);
    provider.ready = Completer<CycleRoute>();
    final retry = model.refreshRoute();
    await Future<void>.delayed(Duration.zero);
    provider.ready.complete(transfer.route);
    expect(await retry, true);
    expect(saved.snapshot, same(transfer));
    expect(model.selectedSavedRoute, same(saved));
    model.setSavedRoutePlan(saved);
    expect(model.isOriginalRoute, true);
    expect(model.route.route, same(transfer.route));
  });
''' + s[insert:]
s = s.replace('final ready = Completer<CycleRoute>();', 'var ready = Completer<CycleRoute>();')
p.write_text(s, encoding='utf-8')
p = root / 'test/model/route_transfer_test.dart'
s = p.read_text(encoding='utf-8').replace('void main() {', '''void main() {
  test('GPX filenames retain names while rejecting filesystem syntax', () {
    expect(RouteTransfer.gpxFilename('GreenCity-über-Hackerbrücke'),
        'GreenCity-über-Hackerbrücke.gpx');
    expect(RouteTransfer.gpxFilename('Tour.gpx'), 'Tour.gpx');
    expect(RouteTransfer.gpxFilename('../Tour: A/B?'), '.._Tour_ A_B_.gpx');
    expect(RouteTransfer.gpxFilename('NUL'), 'MunichWays-Route.gpx');
  });''')
p.write_text(s, encoding='utf-8')
