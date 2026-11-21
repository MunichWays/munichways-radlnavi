// Pure drawing rules, shared by pointer/keyboard interactions and offline tests.
function distance(a, b) {
  return Math.hypot((a[0] - b[0]) * Math.cos((a[1] + b[1]) * Math.PI / 360), a[1] - b[1]) * 111320;
}

export function addDrawingPoint(points, point, tolerance = 1) {
  if (points.length >= 3 && distance(point, points[0]) <= tolerance) return {points, close: true};
  if (points.some(p => distance(point, p) <= tolerance)) return {points, close: false};
  return {points: [...points, point], close: false};
}

export function closeDrawing(points) {
  const vertices = points.map(p => [...p]);
  while (vertices.length > 1 && distance(vertices[0], vertices.at(-1)) < .05) vertices.pop();
  if (vertices.length < 3) throw new Error('Mindestens drei verschiedene Eckpunkte setzen. Vier oder mehr sind ebenfalls möglich.');
  for (let i = 0; i < vertices.length; i++) for (let j = i + 1; j < vertices.length; j++) {
    if (distance(vertices[i], vertices[j]) < .05) throw new Error('Dieser Eckpunkt ist schon vorhanden. Mit „Letzten Punkt entfernen“ korrigieren.');
  }
  const origin = vertices[0], scale = Math.cos(origin[1] * Math.PI / 180);
  const xy = vertices.map(p => [(p[0] - origin[0]) * scale * 111320, (p[1] - origin[1]) * 111320]);
  const ring = [...xy, xy[0]], cross = (a, b, c) => (b[0]-a[0])*(c[1]-a[1]) - (b[1]-a[1])*(c[0]-a[0]);
  const between = (a, b, p) => Math.abs(cross(a,b,p)) < 1e-6 && [0,1].every(k => p[k] >= Math.min(a[k],b[k])-1e-6 && p[k] <= Math.max(a[k],b[k])+1e-6);
  for (let i = 0; i < xy.length; i++) for (let j = i+2; j < xy.length; j++) {
    if (i === 0 && j === xy.length-1) continue;
    const [a,b,c,d] = [ring[i],ring[i+1],ring[j],ring[j+1]];
    if ((cross(a,b,c)*cross(a,b,d)<0 && cross(c,d,a)*cross(c,d,b)<0) || between(a,b,c) || between(a,b,d) || between(c,d,a) || between(c,d,b)) {
      throw new Error('Die Linien kreuzen sich. Letzten Punkt entfernen oder eine neue Fläche zeichnen.');
    }
  }
  const area = Math.abs(xy.reduce((sum, p, i) => sum + p[0]*ring[i+1][1] - p[1]*ring[i+1][0], 0)) / 2;
  if (area < 1) throw new Error('Die Fläche ist zu klein oder die Punkte liegen auf einer Linie. Einen weiteren Eckpunkt abseits der Linie setzen.');
  return [...vertices, [...vertices[0]]];
}
