from html.parser import HTMLParser
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
STATIC = ROOT / "embeddyn" / "local" / "static"


class _IdCollector(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.ids: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        for name, value in attrs:
            if name == "id" and value:
                self.ids.append(value)


def test_rf_cockpit_has_unique_ids_and_visual_analysis_surfaces() -> None:
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    parser = _IdCollector()
    parser.feed(html)
    assert len(parser.ids) == len(set(parser.ids))

    required = {
        "rfOverviewStats",
        "rfConstructionSvg",
        "rfConstructionFacts",
        "rfSystemSources",
        "rfVisualGuidance",
        "rfCursorReadout",
        "rfS11Canvas",
        "rfSmithCanvas",
        "rfNoiseCanvas",
        "rfPeakLadder",
        "rfMatchBadge",
        "rfNoiseBadge",
        "rfOverallBadge",
    }
    assert required.issubset(set(parser.ids))


def test_rf_cockpit_javascript_contains_correlated_views_and_stale_guards() -> None:
    javascript = (STATIC / "app.js").read_text(encoding="utf-8")
    for symbol in (
        "renderRFDashboard",
        "renderRFConstruction",
        "renderRFSystemSources",
        "drawRFS11Chart",
        "drawRFSmithChart",
        "drawRFNoiseSpectrum",
        "rfInstallFrequencyCursor",
        "rfPatchDirty",
        "rfS11Dirty",
        "rfNoiseDirty",
    ):
        assert symbol in javascript


def test_rf_cockpit_styles_are_responsive_and_status_driven() -> None:
    css = (STATIC / "styles.css").read_text(encoding="utf-8")
    for selector in (
        ".rf-overview-grid",
        ".rf-construction-layout",
        ".rf-analysis-grid",
        ".rf-chart-grid",
        ".rf-status-badge.good",
        ".rf-status-badge.warning",
        ".rf-status-badge.danger",
    ):
        assert selector in css
    assert "@media (max-width: 600px)" in css
