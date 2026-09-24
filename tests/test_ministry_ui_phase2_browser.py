"""Real-browser smoke coverage for the institutional presentation layer."""
import threading

import pytest
from flask import Flask
from playwright.sync_api import expect, sync_playwright
from werkzeug.serving import make_server

from kds.api import register_project_api
from kds.data.project_store import FileProjectStore
from test_analysis_workflow import example


@pytest.mark.browser
def test_ministry_workspace_profile_readiness_templates_and_responsive_layout(tmp_path):
    repository = FileProjectStore(tmp_path / "projects"); repository.create(example())
    app = Flask("ministry-ui-browser"); app.config["TESTING"] = True
    register_project_api(app, repository)
    server = make_server("127.0.0.1", 0, app, threaded=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1366, "height": 900})
            errors = []; page.on("pageerror", lambda error: errors.append(str(error)))
            page.goto(f"http://127.0.0.1:{server.server_port}/projects")
            expect(page.locator("#global-mode-badge")).to_contain_text("REFERENCE MODEL")
            expect(page.locator("#mode-warning")).to_be_visible()
            page.locator("#projects .project-card").first.click()
            expect(page.locator("#project-name")).to_have_text(example()["project"]["name"])
            expect(page.locator("#readiness")).to_contain_text("S1: READY")
            expect(page.locator("#template-links a")).to_have_count(19)
            response = page.request.get(f"http://127.0.0.1:{server.server_port}/projects/templates/analysis_units_template.xlsx")
            assert response.ok and "attachment" in response.headers["content-disposition"]
            profile = page.locator('#analysis-form [name="execution_profile"]')
            profile.select_option("VERIFIED_INSTITUTIONAL")
            expect(page.locator("#global-mode-badge")).to_have_text("VERIFIED INSTITUTIONAL")
            expect(page.locator("#mode-warning")).to_be_hidden()
            page.set_viewport_size({"width": 390, "height": 844})
            layout = page.evaluate("""() => ({scroll: document.documentElement.scrollWidth, client: document.documentElement.clientWidth,
              widest: [...document.querySelectorAll('*')].map(e => ({tag:e.tagName,id:e.id,cls:e.className,width:e.getBoundingClientRect().width,right:e.getBoundingClientRect().right})).sort((a,b)=>b.right-a.right).slice(0,5)})""")
            assert layout["scroll"] <= layout["client"], layout
            assert not errors
            browser.close()
    finally:
        server.shutdown(); thread.join(timeout=5)
