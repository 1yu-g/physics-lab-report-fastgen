#!/usr/bin/env python3
"""Build and serve a local browser dashboard for page-by-page report review."""
from __future__ import annotations

import argparse
import json
import mimetypes
import sys
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

import fastgen

HTML = """<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>FastGen 报告复核</title><style>
body{margin:0;background:#eef2f6;color:#172033;font-family:"Microsoft YaHei",sans-serif}header{position:sticky;top:0;background:#172033;color:white;padding:14px 20px;z-index:2;display:flex;gap:12px;align-items:center}header button{margin-left:auto}main{max-width:1100px;margin:20px auto;padding:0 14px}.page{background:white;border-radius:12px;padding:16px;margin:18px 0;box-shadow:0 3px 14px #20304a18}.page.pass{outline:3px solid #2e8b57}.page img{display:block;max-width:100%;margin:auto;border:1px solid #ccd3dd}.toolbar{display:flex;gap:10px;align-items:center;margin-bottom:12px}.toolbar textarea{flex:1;min-height:42px}.status{font-weight:700}.hint{color:#58657a}.save{background:#1b67c9;color:white;border:0;border-radius:7px;padding:9px 16px}.passbtn{background:#2e8b57;color:white;border:0;border-radius:6px;padding:7px 12px}.pendingbtn{border:1px solid #9aa7b8;background:white;border-radius:6px;padding:7px 12px}
</style></head><body><header><strong>FastGen 报告逐页复核</strong><span id="summary"></span><button class="save" onclick="saveReview()">保存复核结果</button></header><main><p class="hint">核对范围、封面、断页、图表、水印、题注、公式、单位和正文缩进。只有实际检查过的页面才能标记为通过。</p><div id="pages"></div></main><script>
let review;
async function load(){review=await (await fetch('/api/review')).json();render()}
function render(){const root=document.getElementById('pages');root.innerHTML='';let passed=0;review.pages.forEach(p=>{if(p.status==='pass')passed++;const card=document.createElement('section');card.className='page '+p.status;card.innerHTML=`<div class="toolbar"><span class="status">第 ${p.page} 页</span><button class="passbtn">通过</button><button class="pendingbtn">待检查</button><textarea placeholder="复核备注"></textarea></div><img src="/preview/${p.page}?v=${p.preview_sha256}" alt="第 ${p.page} 页">`;card.querySelector('textarea').value=p.notes||'';card.querySelector('.passbtn').onclick=()=>{p.status='pass';render()};card.querySelector('.pendingbtn').onclick=()=>{p.status='pending';render()};card.querySelector('textarea').oninput=e=>p.notes=e.target.value;root.appendChild(card)});document.getElementById('summary').textContent=`${passed}/${review.pages.length} 页已通过`}
async function saveReview(){const response=await fetch('/api/review',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({docx_sha256:review.docx_sha256,pages:review.pages.map(p=>({page:p.page,status:p.status,notes:p.notes||''}))})});const data=await response.json();if(!response.ok){alert(data.error||'保存失败');return}review=data;render();alert('复核结果已保存')}
load().catch(e=>alert(e));
</script></body></html>"""


def _load_review(workdir: Path):
    workdir = workdir.expanduser().resolve()
    path = workdir / "review.json"
    if not path.is_file():
        raise FileNotFoundError("Run report rendering before opening the review dashboard.")
    review = fastgen.load(path)
    if not review.get("pages"):
        raise ValueError("No rendered page previews are available.")
    if not Path(review["docx"]).is_file() or fastgen.sha256(review["docx"]) != review["docx_sha256"]:
        raise ValueError("The report changed after rendering; render it again.")
    for page in review["pages"]:
        preview = Path(page["preview"])
        if not preview.is_file() or fastgen.sha256(preview) != page.get("preview_sha256"):
            raise ValueError(f"Page preview changed or is missing: {page['page']}")
    return workdir, path, review


def build(workdir: Path):
    workdir, _, review = _load_review(workdir)
    output = workdir / "review-dashboard.html"
    output.write_text(HTML, encoding="utf-8")
    return {"status": "pass", "dashboard": str(output), "pages": len(review["pages"])}


def apply_updates(workdir: Path, payload: dict):
    workdir, path, review = _load_review(workdir)
    if payload.get("docx_sha256") != review["docx_sha256"]:
        raise ValueError("The dashboard belongs to an older report version.")
    current = {int(page["page"]): page for page in review["pages"]}
    updates = payload.get("pages", [])
    if {int(page.get("page", 0)) for page in updates} != set(current):
        raise ValueError("The update must include every rendered page exactly once.")
    for update in updates:
        page = current[int(update["page"])]
        status = update.get("status")
        if status not in {"pending", "pass"}:
            raise ValueError(f"Invalid page status: {status}")
        page["status"] = status
        page["notes"] = str(update.get("notes", "")).strip()
    review["status"] = (
        "ready-to-finalize" if all(page["status"] == "pass" for page in review["pages"])
        else "needs-visual-review"
    )
    fastgen.dump(path, review)
    return review


def serve(workdir: Path, host="127.0.0.1", port=8765, open_browser=False):
    if host not in {"127.0.0.1", "localhost"}:
        raise ValueError("The review server only binds to the local computer.")
    workdir, _, _ = _load_review(workdir)
    build(workdir)

    class Handler(BaseHTTPRequestHandler):
        def _send(self, status, payload, content_type="application/json; charset=utf-8"):
            if isinstance(payload, str):
                body = payload.encode("utf-8")
            else:
                body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            route = urlparse(self.path).path
            try:
                if route == "/":
                    self._send(200, HTML, "text/html; charset=utf-8")
                elif route == "/api/review":
                    self._send(200, _load_review(workdir)[2])
                elif route.startswith("/preview/"):
                    page_number = int(route.rsplit("/", 1)[-1])
                    review = _load_review(workdir)[2]
                    item = next(page for page in review["pages"] if int(page["page"]) == page_number)
                    data = Path(item["preview"]).read_bytes()
                    self.send_response(200)
                    self.send_header("Content-Type", mimetypes.guess_type(item["preview"])[0] or "image/png")
                    self.send_header("Content-Length", str(len(data)))
                    self.end_headers()
                    self.wfile.write(data)
                else:
                    self._send(404, {"error": "not found"})
            except Exception as exc:
                self._send(400, {"error": str(exc)})

        def do_POST(self):
            if urlparse(self.path).path != "/api/review":
                self._send(404, {"error": "not found"})
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if length <= 0 or length > 1_000_000:
                    raise ValueError("Review update is too large.")
                payload = json.loads(self.rfile.read(length))
                self._send(200, apply_updates(workdir, payload))
            except Exception as exc:
                self._send(400, {"error": str(exc)})

        def log_message(self, format, *args):
            return

    server = ThreadingHTTPServer((host, port), Handler)
    url = f"http://{host}:{port}/"
    print(json.dumps({"status": "serving", "url": url, "workdir": str(workdir)},
                     ensure_ascii=False, indent=2))
    if open_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("build")
    p.add_argument("--workdir", type=Path, required=True)
    p = sub.add_parser("apply")
    p.add_argument("--workdir", type=Path, required=True)
    p.add_argument("--input", type=Path, required=True)
    p = sub.add_parser("serve")
    p.add_argument("--workdir", type=Path, required=True)
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8765)
    p.add_argument("--open", action="store_true")
    args = parser.parse_args()
    try:
        if args.command == "build":
            result = build(args.workdir)
        elif args.command == "apply":
            result = apply_updates(args.workdir, fastgen.load(args.input))
        else:
            return serve(args.workdir, args.host, args.port, args.open)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:
        print(f"review_dashboard: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
