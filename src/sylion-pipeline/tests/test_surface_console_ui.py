"""Tests for surface.console_ui module."""
import pytest
from sylion.surface.console_ui import ConsoleUI, get_console_ui
import sylion.surface.console_ui as mod


@pytest.fixture
def ui():
    mod._ui = None
    return ConsoleUI()


class TestConsoleUI:
    def test_register_component(self, ui):
        result = ui.register_component("DashboardPanel", "panel", config={"cols": 12})
        assert "component_id" in result
        assert result["name"] == "DashboardPanel"

    def test_create_layout(self, ui):
        result = ui.create_layout("main_layout", panels=["nav", "content"])
        assert "layout_id" in result
        assert result["name"] == "main_layout"

    def test_list_components(self, ui):
        ui.register_component("Comp1", "widget")
        ui.register_component("Comp2", "panel")
        comps = ui.list_components()
        assert len(comps) >= 2

    def test_list_layouts(self, ui):
        ui.create_layout("layout_a")
        ui.create_layout("layout_b")
        layouts = ui.list_layouts()
        assert len(layouts) >= 2
