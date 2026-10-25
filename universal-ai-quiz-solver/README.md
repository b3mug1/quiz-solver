# Universal AI Quiz Solver

A Chrome Manifest V3 extension and FastAPI backend that suggest answers for **authorized practice quizzes**. The extension extracts questions from the active page, sends only normalized question data to your backend, and shows suggested answers with an explanation and model confidence estimate. It never submits a quiz.

## What works

- Click to Solve, Ctrl + Hover with debounce and cancellation, and Solve All in groups of five (up to 20 questions per action).
- Automatic solving on an authorized practice site after one-time site access is granted. The extension loads on later page visits, scans newly added questions, and selects native controls when **Auto-select suggested answers** is enabled.
- Semantic HTML radio and checkbox groups, select controls, text fields, ARIA choice groups, and simple custom answer buttons. Open Shadow DOM is scanned. Dynamic content is detected on subsequent interactions.
- Gemini structured JSON output, validation of option IDs, retries, timeout handling, token usage capture, persistent SQLite or PostgreSQL cache, and backend authentication.
- Explicit opt-in auto-selection for native inputs and selects on authorized practice pages. Custom buttons are deliberately excluded because they can submit forms.
- Optional sending of readable same-origin question images. Cross-origin images cannot be captured by the page script. Image-only free-response questions, matching, ordering, and complex platform-specific widgets need additional adapters; the detector does not claim reliable coverage for them.

The confidence number is a model estimate, not a calibrated probability. Users should verify suggestions.

## Local setup

1. Install Python 3.12+ and Chrome. From `backend`, create a virtual environment and install dependencies:

   ```powershell
   python -m venv .venv
   .\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
   ```

2. Copy `.env.example` to `.env`. Get an API key from [Google AI Studio](https://aistudio.google.com/app/apikey). Set `GEMINI_API_KEY`, a long random `API_AUTH_SECRET`, and `ALLOWED_ORIGINS=chrome-extension://YOUR_EXTENSION_ID`. The default model is `gemini-3.6-flash`; check the [current Gemini model list](https://ai.google.dev/gemini-api/docs/models) for your account's availability.

3. Start the API from `backend`:

   ```powershell
   .\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
   ```

   Check `http://127.0.0.1:8000/api/v1/health`. Interactive OpenAPI docs are at `/docs`.

4. Open `chrome://extensions`, enable Developer mode, choose **Load unpacked**, and select the `extension` folder. Copy the extension ID from that page into `ALLOWED_ORIGINS` in `.env`, then restart the API.

5. Open the extension's **Settings** page. Enter `http://127.0.0.1:8000` and the same personal token used for `API_AUTH_SECRET`. Save and test. Open `tests/fixtures/standard.html` through a local web server such as `python -m http.server 8765 --directory tests/fixtures`, then open `http://localhost:8765/standard.html`.

6. For automatic answers, open the **quiz website tab** and then the extension popup. Check **I am using an authorized practice quiz**, then **Auto-solve this site when pages open**. Grant Chrome's site access prompt. This also enables **Auto-select suggested answers**. Reload the quiz page: future visits to that site are scanned without opening the popup. Turn off the site switch to stop automatic scanning there. Chrome internal pages such as `chrome://extensions` cannot be scanned.

The Python backend must be running while the extension solves questions. `Offline: Backend unreachable` means the local server is stopped or the Backend URL is wrong. Keep the Uvicorn terminal open during use. Auto-select applies only to supported native choice controls and selects, and the extension never submits the quiz.

The Gemini key stays in the backend environment. The extension stores only the personal backend token in `chrome.storage.local`. For a shared service, issue separate user credentials through an authentication gateway; this single-token backend is intended for a private deployment. Do not place a shared production token in extension source or distribute a configured profile.

## API

All endpoints except health require `Authorization: Bearer <API_AUTH_SECRET>`.

- `POST /api/v1/solve`: one `Question` JSON object.
- `POST /api/v1/solve/batch`: `{ "questions": [Question, ...] }`, maximum 20.
- `GET /api/v1/health`: liveness.
- `GET /api/v1/status`: whether Gemini is configured and the model name.
- `GET /api/v1/models`: configured model name.

Example request:

```json
{"id":"q1","text":"What is 2 + 2?","question_type":"single_choice","options":[{"id":"A","text":"3"},{"id":"B","text":"4"}]}
```

Source page query strings and fragments are omitted so URL tokens are not transmitted. The backend does not log quiz text. Cache entries expire after `CACHE_TTL_SECONDS` and are removed when the cache is next accessed. The backend limits payloads to 4 MB, concurrent model calls to three, and requests to `RATE_LIMIT_PER_MINUTE` per minute for its single token.

## Tests

From the project root:

```powershell
python -m pytest backend/tests tests/e2e -q --basetemp .pytest-tmp
python -m ruff check backend
```

The tests mock Gemini. Browser tests use local HTML fixtures and Playwright's Chromium. End-to-end browser tests exercise the actual extension background worker, content scripts, batch request, highlighting, and automatic selection after navigating to an authorized site. Real Gemini calls require a valid `GEMINI_API_KEY` and are not part of automated tests.

## Docker and Render

For local Docker, copy `backend/.env.example` to `backend/.env`, fill its variables, then run `docker compose up --build` from the project root. Compose binds the API to localhost and persists SQLite in a named volume.

For Render, create a Blueprint from `render.yaml`. Set `GEMINI_API_KEY`, `API_AUTH_SECRET`, `ALLOWED_ORIGINS`, and a managed PostgreSQL `DATABASE_URL` as secret environment values. Render terminates HTTPS; use its HTTPS service URL in extension Settings. The Settings page requests Chrome host access to that backend only when saved. Keep the backend on HTTPS in cloud deployments. If the model is unavailable to your account, set `GEMINI_MODEL` to an available model and restart.

## Vercel

Deploy the **`backend` directory** as the Vercel project root. `index.py` exports the FastAPI app, `.python-version` selects Python 3.12, and `.vercelignore` excludes local secrets, the virtual environment, tests, and SQLite files. Set `GEMINI_API_KEY`, `GEMINI_MODEL`, `API_AUTH_SECRET`, and `ALLOWED_ORIGINS` as Vercel environment variables. Use the extension's `chrome-extension://<ID>` origin for `ALLOWED_ORIGINS`. Configure `DATABASE_URL` with a managed PostgreSQL database for persistent caching. Without it, Vercel uses SQLite in its writable `/tmp` directory; that cache is temporary and may differ between function instances.

This project is linked to `https://universal-ai-quiz-solver.vercel.app`; deploy updates from `backend` with `vercel deploy --prod`. The extension defaults to this HTTPS URL and migrates the previous local default URL once. Its personal API token is the same `API_AUTH_SECRET` configured in Vercel. The Chrome extension itself remains an unpacked browser extension; Vercel hosts the API, not an installable extension package.

## Known boundaries

DOM extraction cannot reliably interpret every custom quiz widget or inaccessible closed Shadow DOM. The app reports a missing question when extraction fails. Cross-origin image pixels are blocked by browser security; text and readable images still work. No proctoring or access-control bypass is implemented. A suggestion can be wrong or uncertain, so it should be reviewed before use.

The local browser tests cover standard HTML and custom buttons; they do not establish correctness on third-party learning platforms. The current deployment configuration is for a private service, with one backend token and process-local rate limiting. Scale-out or multi-user hosting needs a dedicated identity gateway and shared rate limiter.
