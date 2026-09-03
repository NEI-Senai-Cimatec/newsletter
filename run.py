# run.py
import argparse
import logging
import sys
import lmstudio as lms
from utils import clean_legacy_cache, load_existing_articles, save_articles, initialize_model, logger, initialize_model, merge_json_files
from thequantuminsider import thequantuminsider
from quantamagazine import quantamagazine
from quantumzeitgeist import quantumzeitgeist
from insidequantumtechnology import insidequantumtechnology

# Parse command-line arguments
parser = argparse.ArgumentParser(description="Scrape articles and process with LM Studio")
parser.add_argument("--debug", action="store_true", help="Enable debug mode")
parser.add_argument("--ignore-cache", action="store_true", help="Ignore cache and fetch fresh pages")
args = parser.parse_args()

# Configure logging
logging.basicConfig(
    level=logging.DEBUG if args.debug else logging.INFO,
#        level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('console.txt', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

# Log environment details
if args.debug:
    logger.debug(f"Python version: {sys.version}")
    logger.debug(f"lmstudio version: {lms.__version__}")
    try:
        import cloudscraper
        logger.debug(f"cloudscraper version: {cloudscraper.__version__}")
    except ImportError:
        logger.error("cloudscraper not installed. Please install it using 'pip install cloudscraper'")
        sys.exit(1)

def main():
    clean_legacy_cache()
    articles_dict = {}
    load_existing_articles(articles_dict)
    
    model = initialize_model() # False #;
    
    # Call website-specific scraping functions
    thequantuminsider(model, articles_dict, ignore_cache=args.ignore_cache, debug=args.debug)
    #quantamagazine(model, articles_dict, ignore_cache=args.ignore_cache, debug=args.debug)
    #quantumzeitgeist(model, articles_dict, ignore_cache=args.ignore_cache, debug=args.debug)
    
    #insidequantumtechnology(model, articles_dict, ignore_cache=args.ignore_cache, debug=args.debug)
    
    save_articles(articles_dict, sort_order='desc')
        
if __name__ == "__main__":
    main()
    
    
    
#14355