"""Loopback-only form fixture. HTTP tests are infrastructure checks, not UFO runs."""
import argparse
import html
import json
import threading
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

def make_server(run_dir, port=8765):
    run_dir = Path(run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    lock = threading.Lock()
    def event(record):
        record["timestamp"] = datetime.now(timezone.utc).isoformat()
        with lock, (run_dir / "server_events.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def page(self, status, text):
            body = ("<!doctype html><html lang='en'><meta charset='utf-8'>"
                "<title>UFO Baseline Form</title><style>body{font:22px Arial;max-width:760px;"
                "margin:60px auto;background:#f4f6fa;color:#18223b}main{background:white;padding:32px}"
                "label{display:block;margin:20px 0 8px}input,textarea,button{font:22px Arial;padding:12px}"
                "input,textarea{width:90%}button{margin-top:24px}</style><main>" + text + "</main></html>").encode()
            self.send_response(status)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            route = urlsplit(self.path).path
            if route not in ("/success", "/failure", "/submit"):
                self.page(404, "<h1>Not found</h1>")
                return
            event({"event": "page_view", "route": route})
            self.page(200, f"<h1>UFO Baseline Form</h1><p>Local test submission</p>"
                f"<form method='post' action='{route}'>"
                "<label for='name'>Name</label><input id='name' name='name' required autocomplete='off'>"
                "<label for='message'>Message</label><textarea id='message' name='message' required></textarea>"
                "<button type='submit'>Submit</button></form>")

        def do_POST(self):
            route = urlsplit(self.path).path
            size = int(self.headers.get("Content-Length", 0))
            if route not in ("/success", "/failure", "/submit") or size > 16384:
                self.page(400, "<h1>Invalid request</h1>")
                return
            fields = {k: v[0] for k, v in parse_qs(self.rfile.read(size).decode()).items()}
            valid = bool(fields.get("name") and fields.get("message"))
            accepted = valid and route == "/success"
            fake_success = valid and route == "/submit"
            status = 200 if accepted or fake_success else (503 if valid else 400)
            event({"event": "submission", "route": route, "fields": fields,
                   "accepted": accepted, "http_status": status,
                   "persisted": accepted, "ui_claims_saved": accepted or fake_success})
            if accepted:
                with lock, (run_dir / "accepted_submissions.jsonl").open("a", encoding="utf-8") as f:
                    f.write(json.dumps(fields) + "\n")
                self.page(status, "<h1>Submission successful</h1><p>Your data was saved.</p><p>" +
                          html.escape(fields["message"]) + "</p>")
            elif fake_success:
                # Deliberately inconsistent UI; diagnostic events are not business persistence.
                self.page(status, "<h1>Submission successful</h1><p>Your data was saved.</p><p>" +
                          html.escape(fields["message"]) + "</p>")
            else:
                self.page(status, "<h1>Submission failed</h1><p>503: Service unavailable. "
                          "Your data was NOT saved. Stop and report this error.</p>" if valid else
                          "<h1>Missing required fields</h1>")

    return ThreadingHTTPServer(("127.0.0.1", port), Handler)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    server = make_server(args.run_dir, args.port)
    print(f"Fixture: http://127.0.0.1:{server.server_port}", flush=True)
    server.serve_forever()
