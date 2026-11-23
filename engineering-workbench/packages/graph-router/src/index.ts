import type { Point, Rect } from '@ew/core';

export interface RouteOptions {
  grid?: number; // reserved for future grid snapping; sparse router does not scan the grid
  clearance?: number;
  bendPenalty?: number;
  margin?: number;
}

type Direction = 'H' | 'V' | 'X';
interface Edge { to: number; distance: number; dir: Direction; }
interface QueueItem { state: string; score: number; }

function inflate(rect: Rect, amount: number): Rect {
  return { x: rect.x - amount, y: rect.y - amount, width: rect.width + amount * 2, height: rect.height + amount * 2 };
}
function inside(point: Point, rect: Rect): boolean {
  return point.x > rect.x && point.x < rect.x + rect.width && point.y > rect.y && point.y < rect.y + rect.height;
}
function pointKey(point: Point): string { return `${point.x},${point.y}`; }
function stateKey(index: number, dir: Direction): string { return `${index}:${dir}`; }

class MinHeap {
  private data: QueueItem[] = [];
  push(item: QueueItem) {
    this.data.push(item);
    let i = this.data.length - 1;
    while (i > 0) {
      const p = Math.floor((i - 1) / 2);
      if (this.data[p].score <= item.score) break;
      this.data[i] = this.data[p];
      i = p;
    }
    this.data[i] = item;
  }
  pop(): QueueItem | undefined {
    if (!this.data.length) return undefined;
    const top = this.data[0];
    const last = this.data.pop()!;
    if (this.data.length) {
      let i = 0;
      while (true) {
        let child = i * 2 + 1;
        if (child >= this.data.length) break;
        if (child + 1 < this.data.length && this.data[child + 1].score < this.data[child].score) child += 1;
        if (this.data[child].score >= last.score) break;
        this.data[i] = this.data[child];
        i = child;
      }
      this.data[i] = last;
    }
    return top;
  }
  get size() { return this.data.length; }
}

function segmentClear(a: Point, b: Point, obstacles: Rect[]): boolean {
  if (a.x !== b.x && a.y !== b.y) return false;
  for (const rect of obstacles) {
    if (a.x === b.x) {
      const y1 = Math.min(a.y, b.y), y2 = Math.max(a.y, b.y);
      if (a.x > rect.x && a.x < rect.x + rect.width && y2 > rect.y && y1 < rect.y + rect.height) return false;
    } else {
      const x1 = Math.min(a.x, b.x), x2 = Math.max(a.x, b.x);
      if (a.y > rect.y && a.y < rect.y + rect.height && x2 > rect.x && x1 < rect.x + rect.width) return false;
    }
  }
  return true;
}

function compress(points: Point[]): Point[] {
  if (points.length <= 2) return points;
  const result = [points[0]];
  for (let i = 1; i < points.length - 1; i += 1) {
    const a = result[result.length - 1], b = points[i], c = points[i + 1];
    if ((a.y === b.y) !== (b.y === c.y)) result.push(b);
  }
  result.push(points.at(-1)!);
  return result;
}

/**
 * Sparse rectilinear visibility router. Candidate x/y lines come from endpoint
 * coordinates and inflated obstacle boundaries, then Dijkstra minimizes length
 * plus bend cost. This keeps routing deterministic and fast for dense UI use.
 */
export function routeOrthogonal(source: Point, target: Point, obstacles: Rect[], options: RouteOptions = {}): Point[] {
  const clearance = options.clearance ?? 10;
  const bendPenalty = options.bendPenalty ?? 28;
  const margin = options.margin ?? 80;
  const inflated = obstacles.map((rect) => inflate(rect, clearance));
  const xs = new Set<number>([source.x, target.x, Math.min(source.x, target.x) - margin, Math.max(source.x, target.x) + margin]);
  const ys = new Set<number>([source.y, target.y, Math.min(source.y, target.y) - margin, Math.max(source.y, target.y) + margin]);
  for (const rect of inflated) {
    xs.add(rect.x); xs.add(rect.x + rect.width);
    ys.add(rect.y); ys.add(rect.y + rect.height);
  }
  const xList = [...xs].sort((a, b) => a - b), yList = [...ys].sort((a, b) => a - b);
  const points: Point[] = [];
  const byKey = new Map<string, number>();
  for (const y of yList) for (const x of xList) {
    const point = { x, y };
    if (inflated.some((rect) => inside(point, rect)) && pointKey(point) !== pointKey(source) && pointKey(point) !== pointKey(target)) continue;
    byKey.set(pointKey(point), points.length);
    points.push(point);
  }
  const sourceIndex = byKey.get(pointKey(source)), targetIndex = byKey.get(pointKey(target));
  if (sourceIndex === undefined || targetIndex === undefined) return [source, { x: (source.x + target.x) / 2, y: source.y }, { x: (source.x + target.x) / 2, y: target.y }, target];

  const graph: Edge[][] = points.map(() => []);
  for (const y of yList) {
    const row = points.map((p, i) => ({ p, i })).filter((v) => v.p.y === y).sort((a, b) => a.p.x - b.p.x);
    for (let j = 0; j < row.length - 1; j += 1) {
      const a = row[j], b = row[j + 1];
      if (segmentClear(a.p, b.p, inflated)) {
        const distance = Math.abs(b.p.x - a.p.x);
        graph[a.i].push({ to: b.i, distance, dir: 'H' }); graph[b.i].push({ to: a.i, distance, dir: 'H' });
      }
    }
  }
  for (const x of xList) {
    const col = points.map((p, i) => ({ p, i })).filter((v) => v.p.x === x).sort((a, b) => a.p.y - b.p.y);
    for (let j = 0; j < col.length - 1; j += 1) {
      const a = col[j], b = col[j + 1];
      if (segmentClear(a.p, b.p, inflated)) {
        const distance = Math.abs(b.p.y - a.p.y);
        graph[a.i].push({ to: b.i, distance, dir: 'V' }); graph[b.i].push({ to: a.i, distance, dir: 'V' });
      }
    }
  }

  const heap = new MinHeap();
  const startState = stateKey(sourceIndex, 'X');
  const dist = new Map<string, number>([[startState, 0]]);
  const parent = new Map<string, string>();
  heap.push({ state: startState, score: 0 });
  let finalState: string | undefined;

  while (heap.size) {
    const current = heap.pop()!;
    if (current.score !== dist.get(current.state)) continue;
    const [indexText, directionText] = current.state.split(':');
    const index = Number(indexText), direction = directionText as Direction;
    if (index === targetIndex) { finalState = current.state; break; }
    for (const edge of graph[index]) {
      const nextState = stateKey(edge.to, edge.dir);
      const nextScore = current.score + edge.distance + (direction !== 'X' && direction !== edge.dir ? bendPenalty : 0);
      if (nextScore < (dist.get(nextState) ?? Number.POSITIVE_INFINITY)) {
        dist.set(nextState, nextScore); parent.set(nextState, current.state); heap.push({ state: nextState, score: nextScore });
      }
    }
  }
  if (!finalState) return [source, { x: (source.x + target.x) / 2, y: source.y }, { x: (source.x + target.x) / 2, y: target.y }, target];

  const route: Point[] = [];
  let cursor: string | undefined = finalState;
  while (cursor) {
    const index = Number(cursor.split(':')[0]); route.push(points[index]); cursor = parent.get(cursor);
  }
  route.reverse(); route[0] = source; route[route.length - 1] = target;
  return compress(route);
}

export function polylinePath(points: Point[]): string {
  if (!points.length) return '';
  return `M ${points.map((point) => `${point.x} ${point.y}`).join(' L ')}`;
}

export function routeIntersectsRect(points: Point[], rect: Rect): boolean {
  for (let i = 0; i < points.length - 1; i += 1) {
    const a = points[i], b = points[i + 1];
    if (a.x === b.x) {
      const y1 = Math.min(a.y, b.y), y2 = Math.max(a.y, b.y);
      if (a.x > rect.x && a.x < rect.x + rect.width && y2 > rect.y && y1 < rect.y + rect.height) return true;
    } else if (a.y === b.y) {
      const x1 = Math.min(a.x, b.x), x2 = Math.max(a.x, b.x);
      if (a.y > rect.y && a.y < rect.y + rect.height && x2 > rect.x && x1 < rect.x + rect.width) return true;
    }
  }
  return false;
}
