"""
Knight's Eye — Interactive OSINT Network Graph
Serves an interactive Sigma.js visualization of the collector's contact network.
Dual-use: browser UI for Operator, JSON API for AI agent (MCP).

Usage:
    python -m seithar.knight_eye [--port 8099] [--host 0.0.0.0]
"""

import sqlite3
import json
import re
import math
import os
import argparse
from collections import defaultdict
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
import urllib.parse

DB_PATH = os.path.expanduser("~/.seithar/collector.db")


def get_db():
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA busy_timeout=5000")
    return db


def build_graph_data():
    """Build full network graph from collector DB."""
    db = get_db()

    # Get contacts
    contacts = db.execute("""
        SELECT c.handle, c.display_name, c.follower_count, c.bio, c.tags,
               c.first_seen, c.last_seen,
               COUNT(o.id) as obs_count
        FROM contacts c
        LEFT JOIN observations o ON LOWER(o.author_handle) = LOWER(c.handle)
        GROUP BY c.handle
        ORDER BY obs_count DESC
    """).fetchall()

    contact_set = {r["handle"].lower() for r in contacts}

    # Build edges from @mentions (skip RTs)
    edge_counts = defaultdict(int)
    rows = db.execute(
        "SELECT author_handle, content FROM observations WHERE content LIKE '%@%'"
    ).fetchall()

    for row in rows:
        content = row["content"] or ""
        author = (row["author_handle"] or "").lower()
        if content.startswith("RT @"):
            continue
        mentions = re.findall(r"@(\w+)", content)
        for m in mentions:
            ml = m.lower()
            if ml != author and ml in contact_set:
                edge_counts[(author, ml)] += 1

    # Compute network metrics
    in_degree = defaultdict(int)
    out_degree = defaultdict(int)
    weighted_in = defaultdict(int)
    neighbors = defaultdict(set)

    for (src, tgt), w in edge_counts.items():
        out_degree[src] += 1
        in_degree[tgt] += 1
        weighted_in[tgt] += w
        neighbors[src].add(tgt)
        neighbors[tgt].add(src)

    # Betweenness approximation: bridge nodes connect otherwise separate clusters
    # Simple proxy: nodes whose removal would most reduce connectivity
    all_handles = [r["handle"].lower() for r in contacts]

    # Build nodes
    nodes = []
    max_followers = max((r["follower_count"] or 0) for r in contacts) or 1
    max_obs = max((r["obs_count"] or 0) for r in contacts) or 1

    for r in contacts:
        h = r["handle"].lower()
        followers = r["follower_count"] or 0
        obs = r["obs_count"] or 0
        degree = len(neighbors.get(h, set()))
        w_in = weighted_in.get(h, 0)

        # Influence score: composite of followers, mentions received, degree
        influence = (
            0.3 * (math.log(followers + 1) / math.log(max_followers + 1))
            + 0.4 * (math.log(w_in + 1) / math.log(max(weighted_in.values() or [1]) + 1))
            + 0.3 * (degree / max(len(neighbors.get(all_handles[0], set())) if all_handles else 1, 1))
        )
        influence = min(influence, 1.0)

        # Vulnerability indicators
        vulns = []
        if degree <= 2 and followers < 5000:
            vulns.append("isolated_node")
        if in_degree.get(h, 0) > out_degree.get(h, 0) * 3:
            vulns.append("passive_consumer")
        if out_degree.get(h, 0) > in_degree.get(h, 0) * 3:
            vulns.append("broadcast_node")
        bridge_ratio = len(neighbors.get(h, set()))
        unique_clusters = set()
        for n in neighbors.get(h, set()):
            # Rough cluster: who are THEIR top neighbors?
            nn = neighbors.get(n, set())
            if nn:
                unique_clusters.add(frozenset(list(nn)[:3]))
        if len(unique_clusters) > 3:
            vulns.append("bridge_node")

        tags = json.loads(r["tags"]) if r["tags"] else []

        nodes.append({
            "id": h,
            "label": r["display_name"] or r["handle"],
            "handle": r["handle"],
            "followers": followers,
            "observations": obs,
            "degree": degree,
            "in_degree": in_degree.get(h, 0),
            "out_degree": out_degree.get(h, 0),
            "weighted_mentions": w_in,
            "influence": round(influence, 3),
            "vulnerabilities": vulns,
            "tags": tags,
            "size": max(3, min(30, 3 + influence * 27)),
        })

    # Build edges (filter to significant ones)
    edges = []
    for (src, tgt), w in edge_counts.items():
        if w >= 3:  # minimum threshold
            edges.append({
                "source": src,
                "target": tgt,
                "weight": w,
                "id": f"{src}->{tgt}",
            })

    # Sort nodes by influence
    nodes.sort(key=lambda n: -n["influence"])

    return {
        "nodes": nodes,
        "edges": edges,
        "meta": {
            "total_contacts": len(contacts),
            "total_edges": len(edges),
            "total_observations": sum(r["obs_count"] for r in contacts),
        }
    }


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Knight's Eye</title>
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body { background: #000; color: #fff; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; overflow: hidden; }
#container { width: 100vw; height: 100vh; position: relative; }
#graph-container { width: 100%; height: 100%; }

#panel {
    position: absolute; top: 16px; right: 16px;
    width: 300px; background: rgba(0,0,0,0.85);
    border: 1px solid rgba(255,255,255,0.1);
    border-radius: 6px; padding: 16px;
    backdrop-filter: blur(10px);
    display: none; z-index: 10;
    max-height: 90vh; overflow-y: auto;
}
#panel h2 { font-size: 13px; color: #fff; margin-bottom: 2px; font-weight: 600; }
#panel .handle { font-size: 11px; color: rgba(255,255,255,0.4); margin-bottom: 10px; }
#panel .stat { display: flex; justify-content: space-between; padding: 3px 0; font-size: 11px; border-bottom: 1px solid rgba(255,255,255,0.05); }
#panel .stat-label { color: rgba(255,255,255,0.35); }
#panel .stat-value { color: rgba(255,255,255,0.8); }
#panel .vulns { margin-top: 10px; }
#panel .vuln-tag {
    display: inline-block; padding: 2px 6px; margin: 2px;
    border-radius: 3px; font-size: 9px;
    background: rgba(255,255,255,0.08); color: rgba(255,255,255,0.5);
    border: 1px solid rgba(255,255,255,0.1);
}
#panel .connections { margin-top: 10px; }
#panel .conn-item { font-size: 11px; padding: 2px 0; color: rgba(255,255,255,0.5); cursor: pointer; }
#panel .conn-item:hover { color: #fff; }
#panel .conn-weight { color: rgba(255,255,255,0.25); font-size: 10px; }

#search-box {
    position: absolute; top: 16px; left: 16px; z-index: 10;
}
#search-box input {
    background: rgba(0,0,0,0.7); border: 1px solid rgba(255,255,255,0.1);
    border-radius: 4px; padding: 7px 12px; color: #fff; font-family: inherit;
    font-size: 12px; width: 200px; outline: none;
}
#search-box input::placeholder { color: rgba(255,255,255,0.2); }
#search-box input:focus { border-color: rgba(255,255,255,0.25); }

#panel-close {
    position: absolute; top: 8px; right: 12px;
    cursor: pointer; color: rgba(255,255,255,0.3);
    font-size: 14px; line-height: 1;
}
#panel-close:hover { color: #fff; }
</style>
</head>
<body>
<div id="container">
    <div id="graph-container"></div>
    <div id="search-box"><input type="text" placeholder="Search..." id="search-input"></div>
    <div id="panel">
        <div id="panel-close">&times;</div>
        <h2 id="p-name"></h2>
        <div class="handle" id="p-handle"></div>
        <div id="p-stats"></div>
        <div class="vulns" id="p-vulns"></div>
        <div class="connections" id="p-conns"></div>
    </div>
</div>

<script src="https://cdnjs.cloudflare.com/ajax/libs/sigma.js/2.4.0/sigma.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/graphology/0.25.4/graphology.umd.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/graphology-layout-forceatlas2@0.10.1/dist/graphology-layout-forceatlas2.min.js"></script>
<script>
(async function() {
    const resp = await fetch('/api/graph');
    const data = await resp.json();
    const graph = new graphology.Graph();

    data.nodes.forEach(n => {
        const inf = n.influence || 0;
        const a = 0.4 + inf * 0.6;
        graph.addNode(n.id, {
            label: n.label,
            x: Math.random() * 1000,
            y: Math.random() * 1000,
            size: n.size,
            color: `rgba(255,255,255,${a})`,
            _data: n,
        });
    });

    const maxW = data.edges.length ? Math.max(...data.edges.map(x => x.weight)) : 1;
    data.edges.forEach(e => {
        if (graph.hasNode(e.source) && graph.hasNode(e.target)) {
            try {
                const norm = Math.log(e.weight + 1) / Math.log(maxW + 1);
                graph.addEdge(e.source, e.target, {
                    size: 0.2 + norm * 1.5,
                    color: `rgba(255,255,255,${0.03 + norm * 0.08})`,
                    weight: e.weight,
                });
            } catch(err) {}
        }
    });

    ForceAtlas2.assign(graph, { iterations: 300, settings: {
        gravity: 1.5, scalingRatio: 15,
        barnesHutOptimize: true, barnesHutTheta: 0.6,
        linLogMode: true, adjustSizes: true, edgeWeightInfluence: 0.5,
    }});

    const container = document.getElementById('graph-container');
    const renderer = new Sigma(graph, container, {
        renderLabels: true,
        labelRenderedSizeThreshold: 8,
        labelFont: "-apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
        labelSize: 11,
        labelColor: { color: 'rgba(255,255,255,0.7)' },
        labelWeight: '400',
        defaultEdgeType: 'line',
        minCameraRatio: 0.08,
        maxCameraRatio: 5,
        enableEdgeEvents: false,
        zIndex: true,
        nodeReducer: (node, attrs) => {
            if (hl && hl !== node && !hlN.has(node))
                return { ...attrs, color: 'rgba(255,255,255,0.04)', label: '' };
            return attrs;
        },
        edgeReducer: (edge, attrs) => {
            if (!hl) return attrs;
            const s = graph.source(edge), t = graph.target(edge);
            if (s !== hl && t !== hl)
                return { ...attrs, color: 'rgba(255,255,255,0.01)' };
            return { ...attrs, color: 'rgba(255,255,255,0.25)', size: attrs.size * 1.5 };
        }
    });

    let hl = null, hlN = new Set(), dragNode = null, dragging = false;

    renderer.on('clickNode', ({ node }) => selectNode(node));

    renderer.getMouseCaptor().on('contextmenu', (e) => {
        e.preventDefault();
        hl = null; hlN = new Set();
        document.getElementById('panel').style.display = 'none';
        renderer.refresh();
    });

    renderer.on('downNode', (e) => { dragging = true; dragNode = e.node; renderer.getCamera().disable(); });
    renderer.getMouseCaptor().on('mousemovebody', (e) => {
        if (!dragging || !dragNode) return;
        const pos = renderer.viewportToGraph(e);
        graph.setNodeAttribute(dragNode, 'x', pos.x);
        graph.setNodeAttribute(dragNode, 'y', pos.y);
    });
    renderer.getMouseCaptor().on('mouseup', () => {
        if (dragging) { dragging = false; dragNode = null; renderer.getCamera().enable(); }
    });

    function selectNode(id) {
        hl = id; hlN = new Set(graph.neighbors(id));
        renderer.refresh();
        const d = graph.getNodeAttribute(id, '_data');
        document.getElementById('p-name').textContent = d.label;
        document.getElementById('p-handle').textContent = '@' + d.handle;
        const stats = [
            ['Followers', d.followers.toLocaleString()],
            ['Observations', d.observations.toLocaleString()],
            ['Influence', d.influence.toFixed(3)],
            ['Degree', d.degree],
            ['Mentions', d.weighted_mentions.toLocaleString()],
        ];
        document.getElementById('p-stats').innerHTML = stats.map(([l,v]) =>
            `<div class="stat"><span class="stat-label">${l}</span><span class="stat-value">${v}</span></div>`
        ).join('');
        document.getElementById('p-vulns').innerHTML = d.vulnerabilities.map(v =>
            `<span class="vuln-tag">${v.replace(/_/g,' ')}</span>`
        ).join('') || '';
        const conns = [];
        graph.forEachEdge(id, (edge, attrs, src, tgt) => {
            const other = src === id ? tgt : src;
            const od = graph.getNodeAttribute(other, '_data');
            conns.push({ id: other, label: od?.label || other, weight: attrs.weight || 1 });
        });
        conns.sort((a,b) => b.weight - a.weight);
        document.getElementById('p-conns').innerHTML =
            conns.slice(0, 15).map(c =>
                `<div class="conn-item" data-id="${c.id}">${c.label} <span class="conn-weight">${c.weight}</span></div>`
            ).join('');
        document.querySelectorAll('.conn-item').forEach(el => {
            el.addEventListener('click', () => selectNode(el.dataset.id));
        });
        document.getElementById('panel').style.display = 'block';
    }

    document.getElementById('panel-close').addEventListener('click', () => {
        hl = null; hlN = new Set();
        document.getElementById('panel').style.display = 'none';
        renderer.refresh();
    });

    const si = document.getElementById('search-input');
    si.addEventListener('input', () => {
        const q = si.value.toLowerCase().trim();
        if (!q) { hl = null; hlN = new Set(); renderer.refresh(); return; }
        graph.forEachNode((node, attrs) => {
            const d = attrs._data;
            if (d.handle.toLowerCase().includes(q) || d.label.toLowerCase().includes(q)) {
                selectNode(node);
                const c = renderer.getNodeDisplayData(node);
                renderer.getCamera().animate({ x: c.x, y: c.y, ratio: 0.3 }, { duration: 300 });
                return;
            }
        });
    });

    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            hl = null; hlN = new Set();
            document.getElementById('panel').style.display = 'none';
            si.value = '';
            renderer.refresh();
        }
    });
})();
</script>
</body>
</html>
"""


class KnightEyeHandler(SimpleHTTPRequestHandler):
    graph_cache = None
    
    def log_message(self, format, *args):
        pass  # silence logs

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        
        if parsed.path == "/" or parsed.path == "/index.html":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(HTML_TEMPLATE.encode())
        
        elif parsed.path == "/api/graph":
            if not KnightEyeHandler.graph_cache:
                KnightEyeHandler.graph_cache = build_graph_data()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps(KnightEyeHandler.graph_cache).encode())
        
        elif parsed.path == "/api/graph/refresh":
            KnightEyeHandler.graph_cache = build_graph_data()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "refreshed"}).encode())
        
        elif parsed.path.startswith("/api/node/"):
            handle = parsed.path.split("/api/node/")[1].lower()
            if not KnightEyeHandler.graph_cache:
                KnightEyeHandler.graph_cache = build_graph_data()
            node = next((n for n in KnightEyeHandler.graph_cache["nodes"] if n["id"] == handle), None)
            if node:
                # Get recent content
                db = get_db()
                recent = db.execute(
                    "SELECT content, observed_at FROM observations WHERE LOWER(author_handle) = ? ORDER BY observed_at DESC LIMIT 10",
                    (handle,)
                ).fetchall()
                result = {**node, "recent_posts": [{"content": r["content"][:300], "date": r["observed_at"]} for r in recent]}
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(result).encode())
            else:
                self.send_response(404)
                self.end_headers()
        
        else:
            self.send_response(404)
            self.end_headers()


def serve(host="0.0.0.0", port=8099, preload=True):
    if preload:
        # Pre-build graph data so first request is instant
        cache_file = Path(__file__).parent.parent / "knight_eye_data.json"
        if cache_file.exists():
            import time
            t0 = time.time()
            with open(cache_file) as f:
                KnightEyeHandler.graph_cache = json.load(f)
            print(f"Loaded cached graph data in {time.time()-t0:.1f}s")
        else:
            print("Building graph data (first run)...")
            KnightEyeHandler.graph_cache = build_graph_data()
            with open(cache_file, "w") as f:
                json.dump(KnightEyeHandler.graph_cache, f)
            print("Graph data cached.")
    server = HTTPServer((host, port), KnightEyeHandler)
    print(f"Knight's Eye serving at http://{host}:{port}")
    server.serve_forever()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Knight's Eye OSINT Network Graph")
    parser.add_argument("--port", type=int, default=8099)
    parser.add_argument("--host", default="0.0.0.0")
    args = parser.parse_args()
    serve(args.host, args.port)
