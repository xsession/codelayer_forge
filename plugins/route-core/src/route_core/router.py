from __future__ import annotations

import heapq
import itertools
import math
from dataclasses import dataclass
from typing import Any

from codelayer_sdk import ValidationError


@dataclass(slots=True, frozen=True)
class Point:
    x: int
    y: int


@dataclass(slots=True, frozen=True)
class Rect:
    x: int
    y: int
    width: int
    height: int

    def expanded(self, clearance: int) -> "Rect":
        return Rect(
            self.x - clearance,
            self.y - clearance,
            self.width + clearance * 2,
            self.height + clearance * 2,
        )

    def contains(self, point: Point) -> bool:
        return self.x <= point.x <= self.x + self.width and self.y <= point.y <= self.y + self.height


DIRECTIONS: tuple[tuple[int, int], ...] = ((1, 0), (-1, 0), (0, 1), (0, -1))


def _point(value: Any, name: str) -> Point:
    if not isinstance(value, dict):
        raise ValidationError(f"{name} must be an object with x and y")
    try:
        return Point(int(value["x"]), int(value["y"]))
    except (KeyError, TypeError, ValueError) as exc:
        raise ValidationError(f"invalid {name}: {value!r}") from exc


def _rect(value: Any) -> Rect:
    if not isinstance(value, dict):
        raise ValidationError("obstacle must be an object")
    try:
        rect = Rect(int(value["x"]), int(value["y"]), int(value["width"]), int(value["height"]))
    except (KeyError, TypeError, ValueError) as exc:
        raise ValidationError(f"invalid obstacle: {value!r}") from exc
    if rect.width < 0 or rect.height < 0:
        raise ValidationError("obstacle width and height must be non-negative")
    return rect


def _snap(point: Point, grid: int) -> Point:
    return Point(round(point.x / grid) * grid, round(point.y / grid) * grid)


def _compress(points: list[Point]) -> list[dict[str, int]]:
    if len(points) <= 2:
        return [{"x": point.x, "y": point.y} for point in points]
    compressed = [points[0]]
    previous_direction = (points[1].x - points[0].x, points[1].y - points[0].y)
    for index in range(1, len(points) - 1):
        current_direction = (
            points[index + 1].x - points[index].x,
            points[index + 1].y - points[index].y,
        )
        if current_direction != previous_direction:
            compressed.append(points[index])
        previous_direction = current_direction
    compressed.append(points[-1])
    return [{"x": point.x, "y": point.y} for point in compressed]


def _segments(points: list[dict[str, int]]) -> list[dict[str, int]]:
    return [
        {"x1": first["x"], "y1": first["y"], "x2": second["x"], "y2": second["y"]}
        for first, second in zip(points, points[1:], strict=False)
    ]


def route(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValidationError("route input must be an object")
    start = _point(payload.get("source"), "source")
    target_value = payload.get("target")
    if target_value is None:
        targets = payload.get("targets", [])
        if not targets:
            raise ValidationError("route requires target or a non-empty targets array")
        target_value = targets[0]
    target = _point(target_value, "target")
    grid = int(payload.get("grid", 10))
    clearance = int(payload.get("clearance", 0))
    bend_penalty = int(payload.get("bendPenalty", 30))
    max_iterations = int(payload.get("maxIterations", 250_000))
    if grid <= 0 or clearance < 0 or bend_penalty < 0 or max_iterations <= 0:
        raise ValidationError("grid/maxIterations must be positive; penalties must be non-negative")

    start = _snap(start, grid)
    target = _snap(target, grid)
    obstacles = [_rect(value).expanded(clearance) for value in payload.get("obstacles", [])]

    def blocked(point: Point) -> bool:
        if point in (start, target):
            return False
        return any(rect.contains(point) for rect in obstacles)

    xs = [start.x, target.x]
    ys = [start.y, target.y]
    for rect in obstacles:
        xs.extend((rect.x, rect.x + rect.width))
        ys.extend((rect.y, rect.y + rect.height))
    margin = max(10 * grid, abs(start.x - target.x) // 2, abs(start.y - target.y) // 2)
    bounds = (
        min(xs) - margin,
        min(ys) - margin,
        max(xs) + margin,
        max(ys) + margin,
    )

    # State: (point, incoming direction index). Direction -1 is the start state.
    start_state = (start, -1)
    frontier: list[tuple[int, int, int, Point, int]] = []
    counter = itertools.count()
    heapq.heappush(frontier, (0, 0, next(counter), start, -1))
    cost: dict[tuple[Point, int], int] = {start_state: 0}
    previous: dict[tuple[Point, int], tuple[Point, int]] = {}
    visited = 0
    final_state: tuple[Point, int] | None = None

    while frontier and visited < max_iterations:
        _, current_cost, _, point, incoming = heapq.heappop(frontier)
        state = (point, incoming)
        if current_cost != cost.get(state):
            continue
        visited += 1
        if point == target:
            final_state = state
            break
        for direction_index, (dx, dy) in enumerate(DIRECTIONS):
            neighbor = Point(point.x + dx * grid, point.y + dy * grid)
            if not (bounds[0] <= neighbor.x <= bounds[2] and bounds[1] <= neighbor.y <= bounds[3]):
                continue
            if blocked(neighbor):
                continue
            step_cost = grid
            if incoming != -1 and incoming != direction_index:
                step_cost += bend_penalty
            next_state = (neighbor, direction_index)
            next_cost = current_cost + step_cost
            if next_cost >= cost.get(next_state, math.inf):
                continue
            cost[next_state] = next_cost
            previous[next_state] = state
            heuristic = abs(target.x - neighbor.x) + abs(target.y - neighbor.y)
            heapq.heappush(
                frontier,
                (next_cost + heuristic, next_cost, next(counter), neighbor, direction_index),
            )

    if final_state is None:
        return {
            "routed": False,
            "points": [],
            "segments": [],
            "cost": None,
            "visitedStates": visited,
            "diagnostics": [{
                "code": "ROUTE_NOT_FOUND",
                "severity": "error",
                "message": "No orthogonal route was found inside the search bounds",
                "source": "route-core",
                "details": {"bounds": bounds, "maxIterations": max_iterations},
            }],
        }

    path = [final_state[0]]
    cursor = final_state
    while cursor != start_state:
        cursor = previous[cursor]
        path.append(cursor[0])
    path.reverse()
    compressed = _compress(path)
    result = {
        "routed": True,
        "points": compressed,
        "segments": _segments(compressed),
        "cost": cost[final_state],
        "length": sum(
            abs(second["x"] - first["x"]) + abs(second["y"] - first["y"])
            for first, second in zip(compressed, compressed[1:], strict=False)
        ),
        "bends": max(0, len(compressed) - 2),
        "visitedStates": visited,
        "diagnostics": [],
    }
    result["validation"] = validate_route({
        "points": compressed,
        "obstacles": payload.get("obstacles", []),
        "clearance": clearance,
    })
    return result


def validate_route(payload: dict[str, Any]) -> dict[str, Any]:
    raw_points = payload.get("points", [])
    points = [_point(point, f"points[{index}]") for index, point in enumerate(raw_points)]
    obstacles = [_rect(value).expanded(int(payload.get("clearance", 0))) for value in payload.get("obstacles", [])]
    diagnostics: list[dict[str, Any]] = []
    if len(points) < 2:
        diagnostics.append({"code": "ROUTE_TOO_SHORT", "severity": "error", "message": "Route needs at least two points"})
    for index, (first, second) in enumerate(zip(points, points[1:], strict=False)):
        if first.x != second.x and first.y != second.y:
            diagnostics.append({
                "code": "ROUTE_NOT_ORTHOGONAL",
                "severity": "error",
                "message": f"Segment {index} is not orthogonal",
            })
        samples: list[Point] = []
        if first.x == second.x:
            low, high = sorted((first.y, second.y))
            samples = [Point(first.x, value) for value in range(low, high + 1)]
        elif first.y == second.y:
            low, high = sorted((first.x, second.x))
            samples = [Point(value, first.y) for value in range(low, high + 1)]
        if any(rect.contains(sample) for rect in obstacles for sample in samples):
            diagnostics.append({
                "code": "ROUTE_OBSTACLE_INTERSECTION",
                "severity": "error",
                "message": f"Segment {index} intersects an obstacle or clearance region",
            })
    return {"valid": not diagnostics, "diagnostics": diagnostics}
