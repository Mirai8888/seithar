"""
Seithar CLI — unified command-line interface.

Entry point for the `seithar` command. Dispatches to module handlers.

Commands:
    seithar scan <url>           Scan a URL for cognitive threats
    seithar scan --text "..."    Scan raw text
    seithar scan --file path     Scan a local file
    seithar inoculate SCT-001    Generate inoculation for a technique
    seithar inoculate --list     List available inoculations
    seithar intel --arxiv        Fetch relevant arXiv papers
    seithar intel --feed <url>   Fetch and score an RSS feed
    seithar taxonomy             Print the full SCT taxonomy
    seithar profile --text "..." Profile text for cognitive patterns

All commands support --json for pipeline integration.

Will contain:
    - _cmd_scan, _cmd_inoculate, _cmd_intel, _cmd_taxonomy, _cmd_profile
    - main() entry point using argparse
"""
