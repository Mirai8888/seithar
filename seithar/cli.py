"""
Seithar CLI — unified command-line interface.
"""
import argparse
import json
import sys


def cmd_serve(args):
    """Start the API server."""
    from seithar.api import serve
    serve(host=args.host, port=args.port)


def cmd_scan(args):
    """Run cognitive threat scanner."""
    from seithar.scanner.scanner import scan_text, scan_url, scan_file, format_report

    if args.text:
        report = scan_text(args.text, source="cli_text")
    elif args.url:
        report = scan_url(args.url)
    elif args.file:
        report = scan_file(args.file)
    else:
        print("Error: provide a URL, --text, or --file", file=sys.stderr)
        sys.exit(1)

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(format_report(report))


def cmd_taxonomy(args):
    """Print the full SCT taxonomy."""
    from seithar.core.taxonomy import SCT_TAXONOMY

    print("╔══════════════════════════════════════════════════╗")
    print("║  SEITHAR COGNITIVE DEFENSE TAXONOMY              ║")
    print("╚══════════════════════════════════════════════════╝")
    print()
    for code, tech in SCT_TAXONOMY.items():
        print(f"  {code}: {tech.name}")
        print(f"    {tech.description}")
        print()
    print("────────────────────────────────────────────────────")
    print("研修生 | Seithar Group Research Division")
    print("────────────────────────────────────────────────────")


def cmd_intel(args):
    """Run threat intelligence gathering."""
    if args.arxiv:
        from seithar.intel.arxiv import fetch_arxiv_papers

        print("Fetching arXiv papers...")
        papers = fetch_arxiv_papers()
        print(f"Found {len(papers)} relevant papers\n")

        if not papers:
            print("  No papers matched scoring threshold.")
            return

        for i, p in enumerate(papers[:15], 1):
            print(f"  [{p['score']:.0f}] {p['title'][:90]}")
            print(f"       Keywords: {', '.join(p['matched_keywords'][:5])}")
            print(f"       {p['link']}")
            print()

        if args.json:
            print(json.dumps(papers, indent=2))
    else:
        print("Specify --arxiv (more sources coming soon)", file=sys.stderr)
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        prog="seithar",
        description="Seithar — Cognitive warfare defense and analysis platform.",
    )
    parser.add_argument("--json", action="store_true", help="JSON output")
    sub = parser.add_subparsers(dest="command")

    # scan
    scan_p = sub.add_parser("scan", help="Scan content for cognitive threats")
    scan_p.add_argument("url", nargs="?", help="URL to scan")
    scan_p.add_argument("--text", help="Raw text to scan")
    scan_p.add_argument("--file", help="File to scan")
    scan_p.add_argument("--json", action="store_true", dest="json", help="JSON output")

    # taxonomy
    sub.add_parser("taxonomy", help="Print SCT taxonomy")

    # intel
    intel_p = sub.add_parser("intel", help="Threat intelligence")
    intel_p.add_argument("--arxiv", action="store_true", help="Fetch from arXiv")
    intel_p.add_argument("--json", action="store_true", dest="json", help="JSON output")

    # inoculate (stub)
    inoc_p = sub.add_parser("inoculate", help="Generate inoculation")
    inoc_p.add_argument("code", nargs="?", help="SCT code")
    inoc_p.add_argument("--list", action="store_true", help="List available")

    # profile (stub)
    prof_p = sub.add_parser("profile", help="Profile text")
    prof_p.add_argument("--text", help="Text to profile")

    # serve
    serve_p = sub.add_parser("serve", help="Start API server")
    serve_p.add_argument("--host", default="0.0.0.0", help="Bind address")
    serve_p.add_argument("--port", type=int, default=8900, help="Port")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(0)

    dispatch = {
        "scan": cmd_scan,
        "taxonomy": cmd_taxonomy,
        "intel": cmd_intel,
        "serve": cmd_serve,
    }

    handler = dispatch.get(args.command)
    if handler:
        handler(args)
    else:
        raise NotImplementedError(f"Command '{args.command}' not yet implemented")


if __name__ == "__main__":
    main()
