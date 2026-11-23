import { describe, expect, it } from 'vitest';
import { routeIntersectsRect, routeOrthogonal } from '@ew/router';

describe('orthogonal router', () => {
  it('avoids an obstacle between endpoints', () => {
    const obstacle = { x: 120, y: 40, width: 100, height: 100 };
    const points = routeOrthogonal({ x: 20, y: 90 }, { x: 320, y: 90 }, [obstacle], { grid: 10, clearance: 10 });
    expect(routeIntersectsRect(points, obstacle)).toBe(false);
    expect(points[0]).toEqual({ x: 20, y: 90 });
    expect(points.at(-1)).toEqual({ x: 320, y: 90 });
  });

  it('uses only orthogonal segments', () => {
    const points = routeOrthogonal({ x: 10, y: 20 }, { x: 220, y: 170 }, [], { grid: 10 });
    for (let i = 0; i < points.length - 1; i += 1) {
      expect(points[i].x === points[i + 1].x || points[i].y === points[i + 1].y).toBe(true);
    }
  });
});
