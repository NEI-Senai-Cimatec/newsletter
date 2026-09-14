# run.py
"""CLI entry point: scrape portals and process articles with an LLM API.

Reads provider/model/portals from the user config (``~/.newsletter_tool/``),
overridable via command-line flags. Prefer the desktop GUI (``main.py``) for
interactive use; this CLI is kept for headless operation and debugging.
"""
import argparse
import logging
import sys

from core.api_client import APIClient
from core.config_manager import ConfigManager
from core.utils import (
    ARTICLES_JSON,
    clean_legacy_cache,
    ensure_directories,
    load_existing_articles,
    logger,
    save_articles,
)
from scrapers.insidequantumtechnology import insidequantumtechnology
from scrapers.quantamagazine import quantamagazine
from scrapers.quantumzeitgeist import quantumzeitgeist
from scrapers.thequantuminsider import thequantuminsider

PORTAL_FUNCTIONS = {
    "thequantuminsider": thequantuminsider,
    "quantamagazine": quantamagazine,
    "quantumzeitgeist": quantumzeitgeist,
    "insidequantumtechnology": insidequantumtechnology,
}


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Scrape articles and process them with an LLM API"
    )
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    parser.add_argument("--ignore-cache", action="store_true",
                        help="Ignore cache and fetch fresh pages")
    parser.add_argument("--provider", default=None, help="LLM provider key (e.g. groq)")
    parser.add_argument("--model", default=None, help="Model name (defaults to provider default)")
    parser.add_argument("--api-key", default=None, help="API key (defaults to stored key)")
    parser.add_argument("--min-date", default=None,
                        help="Process articles from this date on (YYYY-MM-DD or YYYY-MM)")
    parser.add_argument("--portals", default=None,
                        help="Comma-separated portal keys (default: enabled in config)")
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('console.txt', encoding='utf-8'),
            logging.StreamHandler()
        ]
    )

    if args.debug:
        logger.debug(f"Python version: {sys.version}")

    manager = ConfigManager()
    config = manager.load()

    provider = args.provider or config["provider"]
    model_name = args.model or config["model"]
    api_key = args.api_key or manager.get_api_key(provider)
    min_date = args.min_date
    if min_date is None:
        min_date = config["scraper_settings"].get("min_date", "")
    if args.portals:
        enabled = [p.strip() for p in args.portals.split(",") if p.strip()]
    else:
        enabled = [key for key, on in config["portals"].items() if on]

    model = APIClient(
        provider=provider,
        api_key=api_key or "",
        model=model_name,
        base_url=config.get("custom_endpoint") or None,
        **config.get("llm_settings", {}),
    )
    logger.info(f"Using provider {provider} with model {model.model}")

    ensure_directories()
    clean_legacy_cache()
    articles_dict = {}
    load_existing_articles(articles_dict, ARTICLES_JSON)

    for portal_key in enabled:
        portal_fn = PORTAL_FUNCTIONS.get(portal_key)
        if portal_fn is None:
            logger.error(f"Unknown portal: {portal_key} (skipping)")
            continue
        portal_fn(model, articles_dict, ignore_cache=args.ignore_cache,
                  debug=args.debug, min_date=min_date)

    save_articles(articles_dict, sort_order='desc', output_file=ARTICLES_JSON)


if __name__ == "__main__":
    main()
