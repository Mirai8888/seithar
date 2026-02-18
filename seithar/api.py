"""
Seithar API — lightweight HTTP server.

Endpoints:
    POST /scan          Scan text or URL for cognitive threats
    POST /inoculate     Generate inoculation for an SCT code
    GET  /taxonomy      Return full SCT taxonomy
    POST /intel/arxiv   Fetch and score recent arxiv papers
    GET  /health        Health check

Usage:
    seithar serve [--host 0.0.0.0] [--port 8900]
"""
import json
import sys
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse

from seithar.scanner.scanner import scan_text, scan_url
from seithar.core.taxonomy import SCT_TAXONOMY
from seithar.inoculator.inoculator import inoculate


class SeitharHandler(BaseHTTPRequestHandler):
    """Minimal HTTP handler. No framework dependencies."""

    def _json(self, code, data):
        body = json.dumps(data, indent=2).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _read_body(self):
        length = int(self.headers.get("Content-Length", 0))
        if length == 0:
            return {}
        raw = self.rfile.read(length)
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {}

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        path = urlparse(self.path).path.rstrip("/")

        if path == "/health":
            self._json(200, {"status": "ok", "service": "seithar"})

        elif path == "/taxonomy":
            taxonomy = {}
            for code, tech in SCT_TAXONOMY.items():
                taxonomy[code] = {
                    "name": tech.name,
                    "description": tech.description,
                }
            self._json(200, {"taxonomy": taxonomy})

        else:
            self._json(404, {"error": "not found"})

    def do_POST(self):
        path = urlparse(self.path).path.rstrip("/")
        body = self._read_body()

        if path == "/scan":
            text = body.get("text")
            url = body.get("url")
            if text:
                result = scan_text(text, source="api")
            elif url:
                try:
                    result = scan_url(url)
                except Exception as e:
                    self._json(400, {"error": f"fetch failed: {str(e)[:200]}"})
                    return
            else:
                self._json(400, {"error": "provide 'text' or 'url' in request body"})
                return
            self._json(200, result)

        elif path == "/inoculate":
            code = body.get("code")
            if not code:
                self._json(400, {"error": "provide 'code' (e.g. SCT-001)"})
                return
            if code not in SCT_TAXONOMY:
                self._json(400, {"error": f"unknown code: {code}"})
                return
            try:
                result = inoculate(code)
                self._json(200, result)
            except NotImplementedError:
                tech = SCT_TAXONOMY[code]
                self._json(200, {
                    "code": code,
                    "name": tech.name,
                    "status": "stub",
                    "message": "inoculation generation not yet implemented for this technique"
                })

        elif path == "/intel/arxiv":
            try:
                from seithar.intel.arxiv import fetch_arxiv_papers
                papers = fetch_arxiv_papers()
                self._json(200, {"papers": papers, "count": len(papers)})
            except Exception as e:
                self._json(500, {"error": str(e)[:300]})

        else:
            self._json(404, {"error": "not found"})

    def log_message(self, format, *args):
        sys.stderr.write(f"[seithar-api] {args[0]} {args[1]} {args[2]}\n")


def serve(host="0.0.0.0", port=8900):
    """Start the Seithar API server."""
    server = HTTPServer((host, port), SeitharHandler)
    print(f"[seithar-api] listening on {host}:{port}")
    print(f"[seithar-api] endpoints: /scan /inoculate /taxonomy /intel/arxiv /health")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[seithar-api] shutdown")
        server.server_close()
