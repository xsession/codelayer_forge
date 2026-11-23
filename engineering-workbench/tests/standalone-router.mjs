import assert from 'node:assert/strict';
import { routeIntersectsRect, routeOrthogonal } from '../standalone/router.js';

const obstacle = { x: 120, y: 40, width: 100, height: 100 };
const route = routeOrthogonal({ x: 20, y: 90 }, { x: 320, y: 90 }, [obstacle], { clearance: 10 });
assert.equal(routeIntersectsRect(route, obstacle), false, 'route intersects obstacle');
assert.deepEqual(route[0], { x: 20, y: 90 });
assert.deepEqual(route.at(-1), { x: 320, y: 90 });
for (let i = 0; i < route.length - 1; i++) assert.ok(route[i].x === route[i+1].x || route[i].y === route[i+1].y, 'non-orthogonal segment');
console.log('standalone router: PASS', route);
