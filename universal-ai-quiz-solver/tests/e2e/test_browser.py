import functools
import http.server
import json
import threading
from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
CHROME = Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe")
SCRIPTS = [
    "site-adapters.js", "question-parser.js", "question-detector.js",
    "answer-highlighter.js", "interaction-handler.js", "content.js",
]


@pytest.fixture(scope="module")
def fixture_server():
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(ROOT / "tests" / "fixtures"))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()


@pytest.mark.skipif(not CHROME.exists(), reason="Chrome not installed")
def test_detection_click_hover_batch(fixture_server):
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(executable_path=str(CHROME), headless=True, args=["--no-sandbox"])
        page = browser.new_page()
        page.add_init_script("""
          window.chrome = {
            storage: {local: {get: async () => ({enabled:true,clickMode:true,hoverMode:true,explanations:true,highlights:true}), set: async () => {}}, onChanged:{addListener:()=>{}}},
            runtime: {onMessage:{addListener:()=>{}}, sendMessage: async (msg) => {
              if (msg.type === 'SOLVE') return {question_id:msg.question.id,question_type:msg.question.question_type,selected_option_ids:[msg.question.options[1]?.id],explanation:'Mock explanation',confidence:.9,status:'solved'};
              if (msg.type === 'BATCH') return {answers:msg.questions.map(q=>({question_id:q.id,question_type:q.question_type,selected_option_ids:[q.options[1]?.id].filter(Boolean),text_answer:q.options.length?null:'mock',explanation:'Mock explanation',confidence:.9,status:'solved'}))};
              return {ok:true};
            }}
          };
        """)
        page.goto(f"{fixture_server}/standard.html")
        page.add_style_tag(path=str(ROOT / "extension" / "styles" / "overlay.css"))
        for script in SCRIPTS:
            page.add_script_tag(path=str(ROOT / "extension" / "content" / script))
        page.wait_for_timeout(350)
        assert page.evaluate("UAQS.detector.detect().length") >= 3
        page.locator("fieldset").first.locator("legend").click()
        page.locator(".uaqs-suggested").first.wait_for()
        assert "Mock explanation" in page.locator("#uaqs-panel").inner_text()
        page.keyboard.down("Control")
        page.locator("fieldset").nth(1).locator("legend").hover()
        page.wait_for_timeout(500)
        page.keyboard.up("Control")
        assert page.locator("#uaqs-results section").count() >= 2
        result = page.evaluate("UAQS.interactions.solveAll()")
        assert result["count"] >= 3
        browser.close()


@pytest.mark.skipif(not CHROME.exists(), reason="Chrome not installed")
def test_extension_loads_in_chrome(tmp_path):
    extension = ROOT / "extension"
    with sync_playwright() as playwright:
        context = playwright.chromium.launch_persistent_context(
            user_data_dir=str(tmp_path / "profile"), headless=True, channel="chromium",
            args=[f"--disable-extensions-except={extension}", f"--load-extension={extension}", "--no-sandbox"],
        )
        worker = context.service_workers[0] if context.service_workers else context.wait_for_event("serviceworker", timeout=30000)
        extension_id = worker.url.split("/")[2]
        page = context.new_page()
        page.goto(f"chrome-extension://{extension_id}/popup/popup.html")
        assert page.locator("h1").inner_text() == "Quiz Solver"
        assert page.locator("#solveAll").is_visible()
        context.close()


@pytest.fixture
def mock_api():
    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass

        def do_POST(self):
            if self.headers.get("Authorization") != "Bearer test-token":
                self.send_error(401)
                return
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            questions = body.get("questions", [body])
            answers = [{"question_id": q["id"], "question_type": q["question_type"],
                        "selected_option_ids": [q["options"][1]["id"]] if q["options"] else [],
                        "text_answer": None if q["options"] else "mock", "explanation": "Mock API explanation",
                        "confidence": 0.9, "status": "solved"} for q in questions]
            result = {"answers": answers} if self.path.endswith("batch") else answers[0]
            payload = json.dumps(result).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://localhost:{server.server_port}"
    server.shutdown()


def test_real_extension_transport(tmp_path, fixture_server, mock_api):
    extension = ROOT / "extension"
    with sync_playwright() as playwright:
        context = playwright.chromium.launch_persistent_context(
            user_data_dir=str(tmp_path / "profile"), headless=True, channel="chromium",
            args=[f"--disable-extensions-except={extension}", f"--load-extension={extension}", "--no-sandbox"],
        )
        worker = context.service_workers[0] if context.service_workers else context.wait_for_event("serviceworker", timeout=30000)
        extension_id = worker.url.split("/")[2]
        quiz = context.new_page()
        quiz.goto(f"{fixture_server}/standard.html")
        popup = context.new_page()
        popup.goto(f"chrome-extension://{extension_id}/popup/popup.html")
        tab_id = popup.evaluate("""async ({backendUrl, quizUrl}) => {
          await chrome.storage.local.set({backendUrl,apiToken:'test-token',enabled:true,clickMode:true,highlights:true,explanations:true});
          const tab = (await chrome.tabs.query({})).find(t => t.url?.startsWith(quizUrl));
          if (!tab) throw new Error('Quiz tab not found');
          const ready = await chrome.runtime.sendMessage({type:'ENSURE',tabId:tab.id});
          if (ready.error) throw new Error(ready.error);
          return tab.id;
        }""", {"backendUrl": mock_api, "quizUrl": fixture_server})
        quiz.wait_for_timeout(150)
        quiz.locator("fieldset").first.locator("legend").click()
        quiz.locator(".uaqs-suggested").first.wait_for()
        result = popup.evaluate("tabId => chrome.tabs.sendMessage(tabId,{type:'SOLVE_ALL'})", tab_id)
        assert result["count"] >= 3, result
        quiz.locator(".uaqs-suggested").first.wait_for()
        assert "Mock API explanation" in quiz.locator("#uaqs-panel").inner_text()
        context.close()


def test_automatic_solve_after_navigation(tmp_path, fixture_server, mock_api):
    extension = ROOT / "extension"
    with sync_playwright() as playwright:
        context = playwright.chromium.launch_persistent_context(
            user_data_dir=str(tmp_path / "profile"), headless=True, channel="chromium",
            args=[f"--disable-extensions-except={extension}", f"--load-extension={extension}", "--no-sandbox"],
        )
        worker = context.service_workers[0] if context.service_workers else context.wait_for_event("serviceworker", timeout=30000)
        popup = context.new_page()
        popup.goto(f"chrome-extension://{worker.url.split('/')[2]}/popup/popup.html")
        result = popup.evaluate("""async ({backendUrl, quizUrl}) => {
          const pattern = 'http://127.0.0.1/*';
          await chrome.storage.local.set({backendUrl,apiToken:'test-token',enabled:true,
            authorizedPractice:true,autoSelect:true,autoSolve:true,autoSites:[pattern],highlights:true});
          return await chrome.runtime.sendMessage({type:'REGISTER_SITE',origin:quizUrl});
        }""", {"backendUrl": mock_api, "quizUrl": fixture_server})
        assert result["ok"], result
        quiz = context.new_page()
        quiz.goto(f"{fixture_server}/standard.html")
        quiz.locator('fieldset:first-of-type input[value="B"]').wait_for(state="attached")
        quiz.wait_for_function("document.querySelector('fieldset input[value=\"B\"]').checked")
        assert "Mock API explanation" in quiz.locator("#uaqs-panel").inner_text()
        quiz.reload()
        quiz.wait_for_function("document.querySelector('fieldset input[value=\"B\"]').checked")
        context.close()
