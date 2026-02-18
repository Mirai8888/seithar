"""
Seithar CLI — unified command-line interface.
"""
import argparse
import sys


def main():
    parser = argparse.ArgumentParser(
        prog="seithar",
        description="Seithar — Cognitive warfare defense and analysis platform.",
    )
    sub = parser.add_subparsers(dest="command")

    scan_p = sub.add_parser("scan", help="Scan content for cognitive threats")
    scan_p.add_argument("url", nargs="?", help="URL to scan")
    scan_p.add_argument("--text", help="Raw text to scan")
    scan_p.add_argument("--file", help="File to scan")

    inoc_p = sub.add_parser("inoculate", help="Generate inoculation")
    inoc_p.add_argument("code", nargs="?", help="SCT code")
    inoc_p.add_argument("--list", action="store_true", help="List available")

    intel_p = sub.add_parser("intel", help="Threat intelligence")
    intel_p.add_argument("--arxiv", action="store_true")
    intel_p.add_argument("--feed", help="RSS feed URL")

    sub.add_parser("taxonomy", help="Print SCT taxonomy")

    prof_p = sub.add_parser("profile", help="Profile text")
    prof_p.add_argument("--text", help="Text to profile")

    parser.add_argument("--json", action="store_true", help="JSON output")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(0)

    raise NotImplementedError(f"Command '{args.command}' not yet implemented")


if __name__ == "__main__":
    main()
