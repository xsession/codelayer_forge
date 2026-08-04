from __future__ import annotations

from typing import Any

from .router import route, validate_route


class RoutingService:
    def route(self, params: dict[str, Any]) -> dict[str, Any]:
        return route(params)

    def validate(self, params: dict[str, Any]) -> dict[str, Any]:
        return validate_route(params)

    def route_bus(self, params: dict[str, Any]) -> dict[str, Any]:
        count = int(params.get("count", 1))
        spacing = int(params.get("spacing", params.get("grid", 10)))
        routes = []
        for index in range(count):
            shifted = dict(params)
            shifted["source"] = dict(params["source"])
            shifted["target"] = dict(params.get("target") or params["targets"][0])
            shifted["source"]["y"] += index * spacing
            shifted["target"]["y"] += index * spacing
            routes.append(route(shifted))
        return {"routed": all(item["routed"] for item in routes), "routes": routes}


class RouteCorePlugin:
    def activate(self, context: Any) -> None:
        self.context = context
        service = RoutingService()
        context.services.register("codelayer.routing.orthogonal", "1.0.0", service)
        context.services.register("codelayer.routing.validation", "1.0.0", service)
        context.commands.register("routeCore.routeSample", self.route_sample)
        context.logger.info("Route Core activated")

    def route_sample(self, arguments: dict[str, Any] | None) -> dict[str, Any]:
        return route(arguments or {
            "source": {"x": 20, "y": 40},
            "target": {"x": 420, "y": 240},
            "obstacles": [{"x": 140, "y": 20, "width": 120, "height": 180}],
            "grid": 10,
            "clearance": 10,
            "bendPenalty": 30,
        })

    def deactivate(self) -> None:
        self.context.logger.info("Route Core deactivated")


def create_plugin() -> RouteCorePlugin:
    return RouteCorePlugin()
