"""Opt-in browser smoke test for the deployed Vercel backend."""

import os
import tempfile
from pathlib import Path

import pytest
from dotenv import dotenv_values
from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[2]
DEPLOYMENT = "https://universal-ai-quiz-solver.vercel.app"


@pytest.mark.skipif(os.getenv("RUN_LIVE_VERCEL") != "1", reason="Live deployment test is opt-in")
def test_extension_reaches_vercel():
    token = dotenv_values(ROOT / "backend" / ".env").get("API_AUTH_SECRET")
    if not token:
        pytest.skip("Local API token is unavailable")
    extension = ROOT / "extension"
    with tempfile.TemporaryDirectory() as profile, sync_playwright() as playwright:
        context = playwright.chromium.launch_persistent_context(
            user_data_dir=profile, headless=True, channel="chromium",
            args=[f"--disable-extensions-except={extension}", f"--load-extension={extension}", "--no-sandbox"],
        )
        worker = context.service_workers[0] if context.service_workers else context.wait_for_event("serviceworker", timeout=30000)
        popup = context.new_page()
        popup.goto(f"chrome-extension://{worker.url.split('/')[2]}/popup/popup.html")
        result = popup.evaluate("""async token => {
          await chrome.storage.local.set({apiToken:token,backendUrl:'http://localhost:8000'});
          const status = await chrome.runtime.sendMessage({type:'STATUS'});
          const stored = await chrome.storage.local.get('backendUrl');
          const answer = await chrome.runtime.sendMessage({type:'SOLVE',question:{
            id:'browser-vercel-smoke',text:'What is 2 + 2?',question_type:'single_choice',
            options:[{id:'A',text:'3'},{id:'B',text:'4'}]
          }});
          return {status,backendUrl:stored.backendUrl,answer};
        }""", token)
        assert result["backendUrl"] == DEPLOYMENT
        assert result["status"]["status"] == "ready"
        assert result["answer"]["selected_option_ids"] == ["B"]
        context.close()
