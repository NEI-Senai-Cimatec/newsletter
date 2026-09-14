# merge.py
"""CLI entry point: consolidate processed articles into the final database.

Thin wrapper over :func:`core.utils.merge_json_files` kept for backward
compatibility with the documented two-step workflow (``run.py`` then
``merge.py``). The desktop GUI performs this step automatically.
"""
import argparse

from core.utils import ARTICLES_JSON, DOCUMENTS_JSON, PARSE_DIR, merge_json_files

# Re-exported so existing imports keep working.
__all__ = ["merge_json_files"]


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Merge parsed article JSON files into the final database"
    )
    parser.add_argument("--articles", default=ARTICLES_JSON,
                        help="Input articles file (default: quantum_articles.json)")
    parser.add_argument("--language", default="en",
                        help="Parse-file language suffix (default: en)")
    parser.add_argument("--parse-dir", default=PARSE_DIR,
                        help="Directory with per-article parse files (default: parse/)")
    parser.add_argument("--output", default=DOCUMENTS_JSON,
                        help="Output database file (default: documents-data.json)")
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    merge_json_files(args.articles, args.language, args.parse_dir, args.output)


if __name__ == "__main__":
    main()
