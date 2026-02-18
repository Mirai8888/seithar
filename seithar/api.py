"""
Seithar API -- cognitive defense analysis platform.

Endpoints:
    POST /v1/scan            Scan text or URL for cognitive threats
    POST /v1/profile         Profile text for cognitive vulnerability surface
    POST /v1/inoculate       Generate mechanism-exposure inoculation
    GET  /v1/taxonomy        Full SCT taxonomy
    POST /v1/intel/arxiv     Fetch scored arxiv papers
    GET  /v1/health          Health check
    GET  /v1/docs            API documentation

All POST endpoints accept JSON. All responses return JSON.
CORS enabled for browser clients.
"""
import json
import sys
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse

from seithar.scanner.scanner import scan_text, scan_url
from seithar.core.taxonomy import SCT_TAXONOMY
from seithar.inoculator.inoculator import inoculate, list_available
from seithar.profiler.profiler import profile_text


_VERSION = "1.0.0"
_START_TIME = None

_DOCS = {
    "service": "Seithar Cognitive Defense API",
    "version": _VERSION,
    "base_url": "/v1",
    "endpoints": {
        "POST /v1/scan": {
            "description": "Scan content for cognitive exploitation techniques",
            "body": {
                "text": "(string) raw text to scan",
                "url": "(string) URL to fetch and scan",
            },
            "note": "Provide either 'text' or 'url', not both",
            "returns": "Threat classification, severity score, detected techniques with confidence and evidence",
        },
        "POST /v1/profile": {
            "description": "Profile text for psychological patterns and SCT vulnerability surface",
            "body": {
                "text": "(string, required) text to profile",
            },
            "returns": "Themes, sentiment, communication style, emotional markers, SCT vulnerability mapping",
        },
        "POST /v1/inoculate": {
            "description": "Generate mechanism-exposure inoculation for an SCT technique",
            "body": {
                "code": "(string, required) SCT code (e.g. SCT-001)",
            },
            "returns": "Mechanism explanation, recognition signals, defense strategy, concrete example",
        },
        "GET /v1/taxonomy": {
            "description": "Return the full Seithar Cognitive Defense Taxonomy",
            "returns": "All 12 SCT codes with names and descriptions",
        },
        "POST /v1/intel/arxiv": {
            "description": "Fetch and score recent arxiv papers for cognitive security relevance",
            "returns": "Scored papers with matched keywords",
        },
        "GET /v1/health": {
            "description": "Health check",
            "returns": "Service status and uptime",
        },
    },
    "taxonomy_codes": [f"SCT-{i:03d}" for i in range(1, 13)],
    "source": "https://github.com/Mirai8888/seithar",
    "attribution": "Seithar Group Research Division",
}


class SeitharHandler(BaseHTTPRequestHandler):

    server_version = f"Seithar/{_VERSION}"

    def _json(self, code, data):
        body = json.dumps(data, indent=2, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
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
            return None

    def _error(self, code, message):
        self._json(code, {"error": message, "status": code})

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()

    def do_GET(self):
        path = urlparse(self.path).path.rstrip("/")

        if path in ("/v1/health", "/health"):
            uptime = round(time.time() - _START_TIME, 1) if _START_TIME else 0
            self._json(200, {
                "status": "ok",
                "service": "seithar",
                "version": _VERSION,
                "uptime_seconds": uptime,
            })

        elif path in ("/v1/taxonomy", "/taxonomy"):
            taxonomy = {}
            for code, tech in SCT_TAXONOMY.items():
                taxonomy[code] = {
                    "name": tech.name,
                    "description": tech.description,
                }
            self._json(200, {
                "taxonomy": taxonomy,
                "count": len(taxonomy),
                "available_inoculations": list_available(),
            })

        elif path in ("/v1/docs", "/docs", "/v1", "/"):
            self._json(200, _DOCS)

        else:
            self._error(404, f"endpoint not found: {path}")

    def do_POST(self):
        path = urlparse(self.path).path.rstrip("/")
        body = self._read_body()

        if body is None:
            self._error(400, "invalid JSON body")
            return

        if path in ("/v1/scan", "/scan"):
            text = body.get("text")
            url = body.get("url")
            if not text and not url:
                self._error(400, "provide 'text' or 'url' in request body")
                return
            try:
                if text:
                    result = scan_text(str(text)[:50000], source="api")
                else:
                    result = scan_url(str(url))
            except Exception as e:
                self._error(502, f"scan failed: {str(e)[:300]}")
                return
            self._json(200, result)

        elif path in ("/v1/profile", "/profile"):
            text = body.get("text")
            if not text:
                self._error(400, "provide 'text' in request body")
                return
            try:
                result = profile_text(str(text)[:50000])
            except Exception as e:
                self._error(500, f"profile failed: {str(e)[:300]}")
                return
            self._json(200, result)

        elif path in ("/v1/inoculate", "/inoculate"):
            code = body.get("code")
            if not code:
                self._error(400, "provide 'code' (e.g. SCT-001)")
                return
            code = str(code).upper()
            if code not in SCT_TAXONOMY:
                self._error(400, f"unknown code: {code}. Valid: SCT-001 through SCT-012")
                return
            result = inoculate(code)
            self._json(200, result)

        elif path in ("/v1/intel/arxiv", "/intel/arxiv"):
            try:
                from seithar.intel.arxiv import fetch_arxiv_papers
                papers = fetch_arxiv_papers()
                self._json(200, {"papers": papers, "count": len(papers)})
            except Exception as e:
                self._error(500, f"arxiv fetch failed: {str(e)[:300]}")

        else:
            self._error(404, f"endpoint not found: {path}")

    def log_message(self, format, *args):
        sys.stderr.write(f"[seithar-api] {args[0]} {args[1]} {args[2]}\n")


def serve(host="0.0.0.0", port=8900):
    """Start the Seithar API server."""
    global _START_TIME
    _START_TIME = time.time()
    server = HTTPServer((host, port), SeitharHandler)
    print(f"[seithar-api] Seithar Cognitive Defense API v{_VERSION}")
    print(f"[seithar-api] listening on {host}:{port}")
    print(f"[seithar-api] docs: http://{host}:{port}/v1/docs")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[seithar-api] shutdown")
        server.server_close()
