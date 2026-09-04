import re
import unittest
from pathlib import Path

from app.version import APP_VERSION


class LongPageUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root = Path(__file__).resolve().parents[1]
        cls.html = (root / "templates" / "index.html").read_text(encoding="utf-8")
        cls.css = (root / "static" / "style.css").read_text(encoding="utf-8")
        cls.v2_css = (root / "static" / "v2.css").read_text(encoding="utf-8")
        cls.js = (root / "static" / "app.js").read_text(encoding="utf-8")

    def test_back_to_top_is_accessible_and_scroll_controlled(self):
        self.assertIn('id="backToTop"', self.html)
        self.assertIn('aria-label="페이지 맨 위로 이동"', self.html)
        self.assertIn("window.scrollY>520", self.js)
        self.assertIn("window.scrollTo({top:0,behavior:'smooth'})", self.js)
        self.assertIn(".back-to-top.visible", self.css)

    def test_quick_navigation_and_simple_view_are_present(self):
        for target in ("firstRunPanel", "requestPanel", "researchPanel", "outlinePanel", "resultPanel", "savedPanel"):
            self.assertIn(f'data-jump="{target}"', self.html)
            self.assertIn(f'id="{target}"', self.html)
        self.assertIn('id="toggleSimpleUi"', self.html)
        self.assertIn('body.simple-ui .optional-panel:not(.force-show)', self.css)
        self.assertIn("localStorage.setItem('sermonSimpleUi'", self.js)

    def test_navigation_selection_and_release_dashboard_are_present(self):
        self.assertIn('data-jump="changesPanel"', self.html)
        self.assertIn('id="changesPanel"', self.html)
        self.assertIn('변경사항 안내', self.html)
        self.assertIn('.side-menu-body button.active', self.v2_css)
        self.assertIn('main>.panel.nav-selected', self.v2_css)
        self.assertIn('classList.toggle(\'active\'', self.js)
        self.assertIn('id="workSummaryPanel"', self.html)
        self.assertIn('id="workSummaryMarkdown"', self.html)
        self.assertIn('id="workSummaryHtml"', self.html)
        self.assertIn('id="workSummaryPrint"', self.html)
        self.assertIn('function printWorkSummary', self.js)
        self.assertIn('print-work-summary', self.js)
        self.assertIn('body.print-work-summary #workSummaryPanel', self.v2_css)
        self.assertIn('body.print-work-summary>main', self.v2_css)

    def test_all_html_ids_are_unique(self):
        ids = re.findall(r'\bid="([^"]+)"', self.html)
        duplicates = sorted({value for value in ids if ids.count(value) > 1})
        self.assertEqual(duplicates, [])

    def test_reduced_motion_and_mobile_navigation_are_supported(self):
        self.assertIn("prefers-reduced-motion:reduce", self.css)
        self.assertIn("overflow-x:auto", self.css)
        self.assertIn("focus-visible", self.css)

    def test_side_menu_has_reachable_reopen_control_and_title_clearance(self):
        self.assertIn('id="toggleSideMenu"', self.html)
        self.assertIn('id="toggleSideMenuTop"', self.html)
        self.assertIn(".side-menu-collapsed .side-menu", self.v2_css)
        self.assertIn(".menu-toggle{display:inline-flex!important", self.v2_css)
        self.assertIn("side-menu-collapsed header", self.v2_css)
        self.assertIn("syncSideMenuState", self.js)
        self.assertIn("localStorage.getItem('sermonSideMenuCollapsed')", self.js)

    def test_ui_assets_are_versioned_to_avoid_stale_browser_cache(self):
        self.assertIn('/static/style.css?v=__APP_VERSION__', self.html)
        self.assertIn('/static/v2.css?v=__APP_VERSION__', self.html)
        self.assertIn('/static/app.js?v=__APP_VERSION__', self.html)
        self.assertRegex(APP_VERSION, r"^\d+\.\d+\.\d+$")


if __name__ == "__main__":
    unittest.main()
