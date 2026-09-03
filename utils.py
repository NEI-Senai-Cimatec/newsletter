# utils.py
import os
from pathlib import Path
import json
import hashlib
from datetime import datetime, timedelta
import shutil
import logging
import traceback
import re
import time
from dateutil.parser import parse as parse_date
import cloudscraper
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import lmstudio as lms
from bs4 import BeautifulSoup

# Logging setup
logger = logging.getLogger(__name__)

# Directories and constants
TEMPLATE_DIR = './template'
CACHE_DIR = "./cache"
LEGACY_CACHE_DIR = "./cache/legacy"
ARTICLE_DIR = "./article"
CONTENT_DIR = "./content"
PARSE_DIR = "./parse"
CACHE_JSON = "./cache.json"
LEGACY_JSON = "./legacy.json"
TTL_DAYS = 30
LEGACY_RETENTION_DAYS = 90

# LLM: Selet model to generate content

LLM_IDENTIFIER = "llama-4-scout-17b-16e-instruct-ud" 
LLM_SETUP = {
    "contextLength": 24576,
    "numExperts": 4,
    "gpu": {
        "ratio": 1.0
    },
    "seed": 662607015 
}

# LLM_IDENTIFIER = "openai/gpt-oss-20b" 
# LLM_SETUP = {
#     "contextLength": 24576,
#     "numExperts": 16,
#     "gpu": {
#         "ratio": 1.0
#     },
#     "seed": 662607015
# }

# LLM_IDENTIFIER = "qwen/qwen3-4b-thinking-2507" 
# LLM_SETUP = {
#     "contextLength": 24576,
#     "gpu": {
#         "ratio": 1.0
#     },
#     "seed": 662607015
# }

# LLM_IDENTIFIER = "baidu/ernie-4.5-21b-a3b" 
# LLM_SETUP = {
#     "contextLength": 24576,
#     "numExperts": 16,
#     "gpu": {
#         "ratio": 1.0
#     },
#     "seed": 662607015
# }
      

      
LLM_CONFIG = {"maxTokens": 10000,
              "temperature": 0.8,
              "topP": 0.95
}
LLM_MAX_INPUT_LENGHT = 24576
LLM_RERUN = False

# Load: HTML template
try:
    template_html = os.path.join(TEMPLATE_DIR, f"html.txt")
    if not template_html or not os.path.exists(template_html):
        logger.error(f"No valid html template file provided.")    
    with open(template_html, "r", encoding="utf-8") as f:
        HTML_TEMPLATE = f.read()
    logger.info("Loaded HTML template from html.txt")
except FileNotFoundError:
    logger.error("html.txt not found")
    raise
except Exception as e:
    logger.error(f"Error loading HTML template: {e}")
    raise

# Load: LLM Parse Prompt
try:
    file_prompt_parse = 'parse_v4.txt'
    prompt_parse = os.path.join(TEMPLATE_DIR, f"{file_prompt_parse}")
    if not prompt_parse or not os.path.exists(prompt_parse):
        logger.error(f"No valid parse template file provided.")    
    with open(prompt_parse, "r", encoding="utf-8") as f:
        LLM_PARSE_PROMPT_PTBR = f.read()
    logger.info(f"Loaded prompt template from {file_prompt_parse}")
except FileNotFoundError:
    logger.error(f"{file_prompt_parse} not found")
    raise
except Exception as e:
    logger.error(f"Error loading prompt template: {e}")
    raise
    
# Load: LLM Parse JSON Schema
try:
    file_schema_parse = 'parse_v4.json'
    schema_parse = os.path.join(TEMPLATE_DIR, f"{file_schema_parse}")
    if not schema_parse or not os.path.exists(schema_parse):
        logger.error(f"No valid json schema parse template file provided.")    
    with open(schema_parse, "r", encoding="utf-8") as f:
        LLM_PARSE_SCHEMA = json.loads(f.read())
    logger.info(f"Loaded json schema parse template from {file_schema_parse}")
except FileNotFoundError:
    logger.error(f"{file_schema_parse} not found")
    raise
except Exception as e:
    logger.error(f"Error loading json schema parse template: {e}")
    raise

# Load: LLM Translation Prompt[PT-BR]
try:
    file_prompt_ptbr = 'translate_ptbr.txt'
    prompt_ptbr = os.path.join(TEMPLATE_DIR, f"{file_prompt_ptbr}")
    if not prompt_ptbr or not os.path.exists(prompt_ptbr):
        logger.error(f"No valid translate prbr template file provided.")    
    with open(prompt_ptbr, "r", encoding="utf-8") as f:
        LLM_TRANSLATE_PROMPT_PTBR = f.read()
    logger.info("Loaded prompt template from {file_prompt_ptbr}")
except FileNotFoundError:
    logger.error(f"{file_prompt_ptbr} not found")
    raise
except Exception as e:
    logger.error(f"Error loading prompt template: {e}")
    raise

# Load: LLM Translation JSON Schema [PT-BR]
try:
    file_schema_ptbr = 'translate_ptbr.json'
    parse_schema_ptbr = os.path.join(TEMPLATE_DIR, f"{file_schema_ptbr}")
    if not parse_schema_ptbr or not os.path.exists(parse_schema_ptbr):
        logger.error(f"No valid json schema parse template file provided.")    
    with open(parse_schema_ptbr, "r", encoding="utf-8") as f:
        LLM_TRANSLATE_SCHEMA_PTBR = json.loads(f.read())
    logger.info(f"Loaded LLM Translation JSON Schema [PT-BR] from {file_schema_ptbr}")
except FileNotFoundError:
    logger.error(f"{file_schema_ptbr} not found")
    raise
except Exception as e:
    logger.error(f"Error loading json schema parse template: {e}")
    raise
    
# Initialize Selenium WebDriver
def initialize_driver():
    options = webdriver.ChromeOptions()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36')
    options.add_experimental_option('excludeSwitches', ['enable-automation'])
    options.add_experimental_option('useAutomationExtension', False)
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
        'source': '''
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            })
        '''
    })
    return driver

# Initialize cloudscraper
scraper = cloudscraper.create_scraper(browser='chrome')

def remove_dupes(sitemap_data):
    """
    Remove duplicate entries from sitemap data based on URL.
    
    Args:
        sitemap_data (list): List of dictionaries containing 'url' and 'date' keys
        
    Returns:
        list: List of unique dictionaries, keeping the latest date for duplicate URLs
    """
    seen_urls = {}
    for item in sitemap_data:
        url = item['url']
        if url in seen_urls:
            # Compare dates and keep the entry with the latest date
            try:
                current_date = datetime.fromisoformat(item['date'].replace('Z', '+00:00'))
                existing_date = datetime.fromisoformat(seen_urls[url]['date'].replace('Z', '+00:00'))
                if current_date > existing_date:
                    seen_urls[url] = item
            except ValueError:
                # If dates are invalid, keep the first occurrence
                continue
        else:
            seen_urls[url] = item
    
    return list(seen_urls.values())


def sortbydate(sitemap_data):
    """
    Sort sitemap data by date in descending order (newest first).
    
    Args:
        sitemap_data (list): List of dictionaries containing 'url' and 'date' keys
        
    Returns:
        list: Sorted list of dictionaries by date
    """
    def get_date(item):
        try:
            # Convert date string to datetime object (handle format like '2025-08-13 15:44 +00:00')
            return datetime.strptime(item['date'], '%Y-%m-%d %H:%M %z')
        except (ValueError, KeyError):
            # Return earliest possible date if date is invalid or missing
            return datetime.min
    
    return sorted(sitemap_data, key=get_date, reverse=True)

def ensure_directories():
    for directory in [TEMPLATE_DIR, CACHE_DIR, LEGACY_CACHE_DIR, ARTICLE_DIR, CONTENT_DIR, PARSE_DIR]:
        if not os.path.exists(directory):
            os.makedirs(directory)
            logger.info(f"Created directory: {directory}")
    for json_file in [CACHE_JSON, LEGACY_JSON]:
        if not os.path.exists(json_file):
            with open(json_file, 'w', encoding='utf-8') as f:
                json.dump([], f)
            logger.info(f"Created empty JSON file: {json_file}")

def get_cache_file_name(url, type_):
    """
    Generate cache file name with type prefix.
    
    Args:
        url (str): URL to hash.
        type_ (str): 'category' or 'article' or 'sitemap'.
    
    Returns:
        str: Cache file name (e.g., 'category_<hash>.html' or 'article_<hash>.html').
    """
    if type_ not in {'category', 'article', 'sitemap'}:
        logger.warning(f"Invalid cache type '{type_}', defaulting to 'article'")
        type_ = 'article'
        
    hash_value = hashlib.sha256(url.encode()).hexdigest()
    
    if type_ == 'sitemap':
        
        return f"{type_}_{hash_value}.xml"

    else:
        
        return f"{type_}_{hash_value}.html"
        
        

def get_cached_page(url, ignore_cache=False, driver=None, type_='article'):
    """
    Fetch a page from cache or live, saving to cache if fetched live.
    Tries Selenium first, falls back to cloudscraper if Cloudflare protection is detected.
    
    Args:
        url (str): URL to fetch.
        ignore_cache (bool): Ignore cache and fetch fresh page.
        driver: Selenium WebDriver instance (optional).
        type_ (str): 'category' or 'article' (default: 'article').
    
    Returns:
        str: Page source content.
    """
    CLOUDFLARE_STRING = 'challenge-error-text'
    cache_file = get_cache_file_name(url, type_)
    cache_path = os.path.join(CACHE_DIR, cache_file)
    cache_data = load_cache_json(CACHE_JSON)
    
    # Check cache first
    if not ignore_cache:
        
        for entry in cache_data:
            
            if entry['url'] == url and entry['type'] == type_ and is_cache_valid(entry):
                if os.path.exists(cache_path):
                    with open(cache_path, 'r', encoding='utf-8') as f:
                        logger.info(f"Loaded cached page: {url} ({type_})")
                        return f.read()
                else:
                    logger.warning(f"Cache file {cache_file} missing for {url}")
    
        if os.path.exists(cache_path):
            
            logger.info(f"Recovery cached page: {url} ({type_})")
           
            cache_data = [entry for entry in cache_data if entry['url'] != url or entry['type'] != type_]
            cache_data.append({
                'url': url,
                'timestamp': datetime.now().isoformat(),
                'file': cache_file,
                'type': type_
            })
            
            save_cache_json(CACHE_JSON, cache_data)
            
            with open(cache_path, 'r', encoding='utf-8') as f:
                logger.info(f"Loaded cached page: {url} ({type_})")
                return f.read() 
    
    logger.info(f"Fetching live page: {url} ({type_})")
    
    # Try cloudscraper
    try:
        response = scraper.get(url)
        response.raise_for_status()
        page_source = response.text
        
        # Save to cache
        with open(cache_path, 'w', encoding='utf-8') as f:
            f.write(page_source)
        
        cache_data = [entry for entry in cache_data if entry['url'] != url or entry['type'] != type_]
        cache_data.append({
            'url': url,
            'timestamp': datetime.now().isoformat(),
            'file': cache_file,
            'type': type_
        })
        save_cache_json(CACHE_JSON, cache_data)
        return page_source
    except Exception as e:
        logger.error(f"Cloudscraper failed for {url}: {e}")
        raise

    # Fallback Selenium
    try:
        driver.get(url)
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.TAG_NAME, 'body'))
        )
        page_source = driver.page_source
        
        # Check for Cloudflare protection
        if CLOUDFLARE_STRING in page_source:
            logger.info("Cloudflare protection detected!")
        else:
            # Save to cache if no Cloudflare
            with open(cache_path, 'w', encoding='utf-8') as f:
                f.write(page_source)
            
            cache_data = [entry for entry in cache_data if entry['url'] != url or entry['type'] != type_]
            cache_data.append({
                'url': url,
                'timestamp': datetime.now().isoformat(),
                'file': cache_file,
                'type': type_
            })
            save_cache_json(CACHE_JSON, cache_data)
            return page_source
        
    except Exception as e:
        logger.error(f"Selenium failed for {url}: {e}")
    
        
def load_cache_json(json_file):
    """
    Load cache JSON, validating type field.
    
    Args:
        json_file (str): Path to JSON file.
    
    Returns:
        list: Cache entries with 'type' field.
    """
    try:
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            if not isinstance(data, list):
                logger.warning(f"Invalid JSON in {json_file}: not a list, initializing empty list")
                return []
            for entry in data:
                if 'type' not in entry or entry['type'] not in {'category', 'article', 'sitemap'}:
                    logger.warning(f"Invalid or missing type in entry: {entry}, defaulting to 'article'")
                    entry['type'] = 'article'
                if not entry['file'].startswith(f"{entry['type']}_"):
                    logger.warning(f"Invalid file name {entry['file']} for type {entry['type']} in {entry['url']}")
            return data
    except (json.JSONDecodeError, FileNotFoundError):
        logger.warning(f"Empty or invalid JSON in {json_file}, initializing empty list")
        return []

def save_cache_json(json_file, cache_data):
    """
    Save cache data to JSON file.
    
    Args:
        json_file (str): Path to JSON file.
        cache_data (list): Cache entries.
    """
    with open(json_file, 'w', encoding='utf-8') as f:
        json.dump(cache_data, f, indent=4, ensure_ascii=False)
    logger.info(f"Saved JSON to {json_file}")

def is_cache_valid(entry):
    """
    Check if a cache entry is still valid based on TTL.
    
    Args:
        entry (dict): Cache entry with 'timestamp'.
    
    Returns:
        bool: True if cache is valid, False otherwise.
    """
    try:
        cache_time = datetime.fromisoformat(entry['timestamp'])
        return datetime.now() - cache_time < timedelta(days=TTL_DAYS)
    except (ValueError, KeyError) as e:
        logger.error(f"Invalid timestamp in cache entry {entry}: {e}")
        return False

def move_to_legacy(entry):
    """
    Move cache file to legacy directory.
    
    Args:
        entry (dict): Cache entry with 'url', 'file', 'timestamp', 'type'.
    """
    cache_file = os.path.join(CACHE_DIR, entry['file'])
    legacy_file = os.path.join(LEGACY_CACHE_DIR, entry['file'])
    if os.path.exists(cache_file):
        shutil.move(cache_file, legacy_file)
        logger.info(f"Moved cache file: {entry['file']} to legacy")
    legacy_data = load_cache_json(LEGACY_JSON)
    legacy_data.append(entry)
    save_cache_json(LEGACY_JSON, legacy_data)

def clean_legacy_cache(retention_days=LEGACY_RETENTION_DAYS):
    """
    Clean legacy cache files older than retention_days.
    
    Args:
        retention_days (int): Number of days to retain legacy files.
    """
    legacy_data = load_cache_json(LEGACY_JSON)
    retained_data = []
    current_time = datetime.now()
    for entry in legacy_data:
        try:
            timestamp = datetime.fromisoformat(entry['timestamp'])
            if current_time - timestamp < timedelta(days=retention_days):
                retained_data.append(entry)
            else:
                legacy_file = os.path.join(LEGACY_CACHE_DIR, entry['file'])
                if os.path.exists(legacy_file):
                    os.remove(legacy_file)
                    logger.info(f"Deleted legacy cache file: {legacy_file}")
        except (ValueError, KeyError) as e:
            logger.error(f"Invalid entry in legacy cache: {entry}, error: {e}")
    save_cache_json(LEGACY_JSON, retained_data)

def generate_content_text(article_hash, debug=False):
    """
    Extract text from the generated article HTML file and save it as a text file.
    
    Args:
        article_hash (str): Unique hash for the article (e.g., SHA256 of URL).
        debug (bool): Enable debug logging.
    
    Returns:
        str: Path to the generated text file, or None if failed.
    """
    try:

        content_file = os.path.join(CONTENT_DIR, f"{article_hash}.txt")
        
        if os.path.exists(content_file):
            logger.info(f"Skip run: keep existing Content TXT {article_hash}")
            return None    

        article_file = os.path.join(ARTICLE_DIR, f"{article_hash}.html")
        
        if not os.path.exists(article_file):
            logger.warning(f"Article file {article_file} not found, skipping TXT generation")
            return None
        
        with open(article_file, 'r', encoding='utf-8') as f:
            html_content = f.read()
        
        if debug:
            debug_html_file = os.path.join(CONTENT_DIR, f"debug_{article_hash}.html")
            with open(debug_html_file, 'w', encoding='utf-8') as f:
                f.write(html_content)
            logger.info(f"Saved input HTML for debugging: {debug_html_file}")
        
        content_soup = BeautifulSoup(html_content, 'html.parser')
        content_div = content_soup.find('div', class_='content')
        
        if content_div:
            text = content_div.get_text(separator='\n', strip=True)
            text = re.sub(r'\n\s*\n+', '\n', text).strip()
            text = re.sub(r'\s+', ' ', text)
            
            if not text:
                logger.warning(f"No text extracted from content div in {article_file}")
                return None
            
            with open(content_file, 'w', encoding='utf-8') as f:
                f.write(text)
            logger.info(f"Generated content TXT: {content_file}")

        else:
            logger.warning(f"No content div found in {article_file}, skipping TXT generation")
            return None
    except Exception as e:
        logger.error(f"Error generating content text for {article_hash}: {e}")
        if debug:
            logger.error(f"Traceback: {traceback.format_exc()}")
        return None

def parse_article_date(date_str):
    """
    Parse article date string into formatted date and timestamp.
    
    Args:
        date_str (str): Date string to parse.
    
    Returns:
        tuple: (formatted_date, iso_timestamp) or (None, None) if invalid.
    """
    try:
        parsed_date = parse_date(date_str, fuzzy=True)
        formatted_date = parsed_date.strftime('%Y-%m-%d')
        iso_timestamp = parsed_date.isoformat()
        return formatted_date, iso_timestamp
    except Exception as e:
        logger.warning(f"Failed to parse date '{date_str}': {e}")
        return None, None

def initialize_model(setup = "llama-4-scout"):
     
    try:
        model = lms.llm(LLM_IDENTIFIER, config = LLM_SETUP)
        logger.info(f"Model initialized: {model.get_info().display_name}")
        return model
    except lms.LMStudioError as e:
        logger.error(f"Failed to initialize model: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error initializing model: {e}")
        raise
              
def sanitize_content(content):
    """
    Sanitize content by removing invalid Unicode characters.
    
    Args:
        content (str): Input content.
    
    Returns:
        str: Sanitized content.
    """
    return content.encode('utf-8', errors='ignore').decode('utf-8')

def clean_unicode_escapes(text):
    """
    Clean Unicode escape sequences from text.
    
    Args:
        text (str): Input text.
    
    Returns:
        str: Cleaned text.
    """
    try:
        return re.sub(r'\\u[0-9a-fA-F]{4}', lambda m: m.group(0).encode().decode('unicode_escape'), text)
    except UnicodeDecodeError:
        logger.warning(f"Failed to decode Unicode escapes in text: {text}")
        return text

def validate_json_unicode(json_obj):
    """
    Recursively clean Unicode issues in JSON object.
    
    Args:
        json_obj: JSON object (dict, list, or primitive).
    
    Returns:
        Cleaned JSON object.
    """
    if isinstance(json_obj, dict):
        return {k: validate_json_unicode(v) for k, v in json_obj.items()}
    elif isinstance(json_obj, list):
        return [validate_json_unicode(item) for item in json_obj]
    elif isinstance(json_obj, str):
        return clean_unicode_escapes(json_obj)
    return json_obj

def validate_classification_weights(json_output, valid_classifications, max_weights):
    """
    Validate classification weights in JSON output.
    
    Args:
        json_output (dict): JSON object with classification and weights.
        valid_classifications (list): list of content classifications.
        max_weights (dict): dict of corresponding max weights for each classification.
    
    Returns:
        dict: Validated JSON object with total_score.
    """
    
    weights = json_output.get("classification_weight", {})
    
    if not isinstance(weights, dict):
        raise ValueError("classification_weight must be a dict")
    
    classification = list(weights.keys())

    json_output["classification"] = []
    
    # Validate classification categories
    for category in classification:
        if category not in valid_classifications:
            raise ValueError(f"Invalid classification category: {category}")
            
    # Validate weights
    for category in valid_classifications:
        if category not in weights:
            weights[category] = 0
        elif not isinstance(weights[category], int):
            raise ValueError(f"Weight for {category} must be an integer")
        elif weights[category] < 0 or weights[category] > max_weights[category]:
            raise ValueError(f"Weight for {category} ({weights[category]}) out of range 0–{max_weights[category]}")       
   
    # Ensure consistency between classification and weights
    for category in valid_classifications:
        if weights.get(category, 0) > 0:
            json_output["classification"].append(category)
    
    total_score = sum(weights.values())
    json_output["total_score"] = total_score
    
    return json_output

def extract_json_from_response(output_text):
    """
    Extract JSON from model response text.
    
    Args:
        output_text (str): Raw model response.
    
    Returns:
        dict: Parsed JSON or None if invalid.
    """
    output_text = clean_unicode_escapes(output_text)
    try:
        return json.loads(output_text.strip())
    except json.JSONDecodeError:
        pass
    match = re.search(r'(?:\s*|\s|^)(\{.*\})$', output_text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1).strip())
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse JSON after regex: {e}")
    match = re.search(r'(\{.*\})', output_text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1).strip())
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse JSON-like structure: {e}")
    return None

def trim_json_whitespace(json_output):
    """
    Trims leading and trailing whitespace from all string fields in the JSON output,
    including nested fields in lists and dictionaries.
    
    Args:
        json_output: The JSON dictionary to process
        
    Returns:
        The modified JSON dictionary with trimmed strings
    """
    def trim_strings(obj):
        if isinstance(obj, str):
            return obj.strip()
        elif isinstance(obj, list):
            return [trim_strings(item) for item in obj]
        elif isinstance(obj, dict):
            return {key: trim_strings(value) for key, value in obj.items()}
        return obj

    if not isinstance(json_output, dict):
        raise ValueError("Input must be a dictionary")
    
    return trim_strings(json_output)

def validate_json_structure(json_output, article_hash, language, debug=False):
    """
    Validate the JSON output against the provided schema.
    
    Args:
        json_output: JSON object to validate.
        article_hash (str): Identifier for the article.
        language (str): Language for validation ('en' or 'ptbr').
        max_retries (int): Maximum retry attempts.
        attempt (int): Current retry attempt.
        debug (bool): Enable debug logging.
    
    Returns:
        dict: Validated JSON object or error details.
    """

    if language == 'ptbr':
        valid_classifications = {"Negócios", "Tecnológico", "Científico", "Outros"}
        max_weights = {"Negócios": 35, "Tecnológico": 35, "Científico": 15, "Outros": 15}    
        valid_event_types = {
            "Forum", "Conference", "Workshop", "Expo", "Open House", "Hackathon",
            "Symposium", "Hybrid Event", "Online Conference", "Speaker Series",
            "Film Screening", "Panel Discussion", "Event", "Webinar", "n/a"
        }
        valid_event_types = {"Fórum", "Conferência", "Workshop", "Exposição", "Casa Aberta", "Hackathon", "Simpósio", "Evento Híbrido", "Conferência Online", "Série de Palestrantes", "Exibição de Filme", "Discussão em Painel", "Evento", "Webinar", "n/a"}
        valid_currencies = ["Dólar dos Estados Unidos (USD), Estados Unidos", "Euro (EUR), Zona do Euro", "Yuan Chinês (CNY), China", "Iene Japonês (JPY), Japão", "Libra Esterlina (GBP), Reino Unido", "Dólar Canadense (CAD), Canadá", "Dólar Australiano (AUD), Austrália", "Franco Suíço (CHF), Suíça", "Dólar de Hong Kong (HKD), Hong Kong", "Dólar Neozelandês (NZD), Nova Zelândia", "Won Sul-Coreano (KRW), Coreia do Sul", "Dólar de Singapura (SGD), Singapura", "Rúpia Indiana (INR), Índia", "Peso Mexicano (MXN), México", "Coroa Norueguesa (NOK), Noruega", "Coroa Sueca (SEK), Suécia", "Rand Sul-Africano (ZAR), África do Sul", "Rublo Russo (RUB), Rússia", "Real Brasileiro (BRL), Brasil", "Lira Turca (TRY), Turquia", "Dinar Kuwaitiano (KWD), Kuwait", "Dinar Bareinita (BHD), Bahrein", "Rial Omanense (OMR), Omã", "Dinar Jordaniano (JOD), Jordânia", "Dólar das Ilhas Cayman (KYD), Ilhas Cayman", "Libra de Gibraltar (GIP), Gibraltar", "Rial Saudita (SAR), Arábia Saudita", "Dirham dos Emirados Árabes Unidos (AED), Emirados Árabes Unidos", "Rial Catariano (QAR), Catar", "Coroa Dinamarquesa (DKK), Dinamarca", "Złoty Polonês (PLN), Polônia", "Baht Tailandês (THB), Tailândia", "Ringgit Malaio (MYR), Malásia", "Novo Shekel Israelense (ILS), Israel", "Rúpia Indonésia (IDR), Indonésia", "Coroa Tcheca (CZK), República Tcheca", "Peso Filipino (PHP), Filipinas", "Peso Chileno (CLP), Chile", "Peso Colombiano (COP), Colômbia", "Peso Argentino (ARS), Argentina", "Forint Húngaro (HUF), Hungria", "Sol Peruano (PEN), Peru", "Libra Egípcia (EGP), Egito", "Rúpia Paquistanesa (PKR), Paquistão", "Dong Vietnamita (VND), Vietnã", "Taka de Bangladesh (BDT), Bangladesh", "Leu Romeno (RON), Romênia", "Hryvnia Ucraniana (UAH), Ucrânia", "Dirham Marroquino (MAD), Marrocos", "Dinar Argelino (DZD), Argélia", "Xelim Queniano (KES), Quênia", "Naira Nigeriana (NGN), Nigéria", "Dólar de Taiwan (TWD), Taiwan", "Rúpia do Sri Lanka (LKR), Sri Lanka", "Lev Búlgaro (BGN), Bulgária", "Kuna Croata (HRK), Croácia", "Dinar Sérvio (RSD), Sérvia", "Dinar Tunisiano (TND), Tunísia", "Cedi Ganês (GHS), Gana", "Kwanza Angolano (AOA), Angola", "Pataca de Macau (MOP), Macau", "Peso Uruguaio (UYU), Uruguai", "Colón Costarriquenho (CRC), Costa Rica", "Peso Dominicano (DOP), República Dominicana", "Coroa Islandesa (ISK), Islândia", "Rublo Bielorrusso (BYN), Belarus", "Libra Libanesa (LBP), Líbano", "Tenge Cazaque (KZT), Cazaquistão", "Som Uzbeque (UZS), Uzbequistão", "Guarani Paraguaio (PYG), Paraguai", "Boliviano Boliviano (BOB), Bolívia", "Lempira Hondurenha (HNL), Honduras", "Quetzal Guatemalteco (GTQ), Guatemala", "Dólar Jamaicano (JMD), Jamaica", "Balboa Panamenha (PAB), Panamá", "Dólar Fijiano (FJD), Fiji", "Dólar Bahamense (BSD), Bahamas", "Dólar Barbadense (BBD), Barbados", "Dólar de Trinidad e Tobago (TTD), Trinidad e Tobago", "Dólar do Caribe Oriental (XCD), Caribe Oriental", "Rúpia Mauriciana (MUR), Maurício", "Pula de Botswana (BWP), Botswana", "Dólar Namibiano (NAD), Namíbia", "Kwacha Zambiano (ZMW), Zâmbia", "Rufiyaa Maldiva (MVR), Maldivas", "Dólar de Brunei (BND), Brunei", "Birr Etíope (ETB), Etiópia", "Rúpia Nepalesa (NPR), Nepal", "Tugrik Mongol (MNT), Mongólia", "Som Quirguiz (KGS), Quirguistão", "Somoni Tadjique (TJS), Tadjiquistão", "Dram Armênio (AMD), Armênia", "Lari Georgiano (GEL), Geórgia", "Manat Azeri (AZN), Azerbaijão", "Dinar Macedônio (MKD), Macedônia do Norte", "Lek Albanês (ALL), Albânia", "Marco Conversível da Bósnia (BAM), Bósnia e Herzegovina", "Leu Moldavo (MDL), Moldávia", "Franco CFA BCEAO (XOF), Estados da África Ocidental", "Libra Britânica (GBP), Reino Unido", "Novo Dólar Taiwanês (NTD), Taiwan", "n/a"]
        
    else:
        valid_classifications = {"Business", "Technological", "Scientific", "Others"}
        max_weights = {"Business": 35, "Technological": 35, "Scientific": 15, "Others": 15}    
        valid_event_types = {
            "Forum", "Conference", "Workshop", "Expo", "Open House", "Hackathon", "Symposium", "Hybrid Event", "Online Conference", "Speaker Series", "Film Screening", "Panel Discussion", "Event", "Webinar", "n/a"
        }
        valid_currencies = ["United States Dollar (USD), United States", "Euro (EUR), Eurozone", "Chinese Yuan (CNY), China", "Japanese Yen (JPY), Japan", "British Pound Sterling (GBP), United Kingdom", "Canadian Dollar (CAD), Canada", "Australian Dollar (AUD), Australia", "Swiss Franc (CHF), Switzerland", "Hong Kong Dollar (HKD), Hong Kong", "New Zealand Dollar (NZD), New Zealand", "South Korean Won (KRW), South Korea", "Singapore Dollar (SGD), Singapore", "Indian Rupee (INR), India", "Mexican Peso (MXN), Mexico", "Norwegian Krone (NOK), Norway", "Swedish Krona (SEK), Sweden", "South African Rand (ZAR), South Africa", "Russian Rubles (RUB), Russia", "Brazilian Real (BRL), Brazil", "Turkish Lira (TRY), Turkey", "Kuwaiti Dinar (KWD), Kuwait", "Bahraini Dinar (BHD), Bahrain", "Omani Rial (OMR), Oman", "Jordanian Dinar (JOD), Jordan", "Cayman Islands Dollar (KYD), Cayman Islands", "Gibraltar Pound (GIP), Gibraltar", "Saudi Riyal (SAR), Saudi Arabia", "United Arab Emirates Dirham (AED), United Arab Emirates", "Qatari Riyal (QAR), Qatar", "Danish Krone (DKK), Denmark", "Polish Zloty (PLN), Poland", "Thai Baht (THB), Thailand", "Malaysian Ringgit (MYR), Malaysia", "Israeli New Shekel (ILS), Israel", "Indonesian Rupiah (IDR), Indonesia", "Czech Koruna (CZK), Czech Republic", "Philippine Peso (PHP), Philippines", "Chilean Peso (CLP), Chile", "Colombian Peso (COP), Colombia", "Argentine Peso (ARS), Argentina", "Hungarian Forint (HUF), Hungary", "Peruvian Sol (PEN), Peru", "Egyptian Pound (EGP), Egypt", "Pakistani Rupee (PKR), Pakistan", "Vietnamese Dong (VND), Vietnam", "Bangladeshi Taka (BDT), Bangladesh", "Romanian Leu (RON), Romania", "Ukrainian Hryvnia (UAH), Ukraine", "Moroccan Dirham (MAD), Morocco", "Algerian Dinar (DZD), Algeria", "Kenyan Shilling (KES), Kenya", "Nigerian Naira (NGN), Nigeria", "Taiwan Dollar (TWD), Taiwan", "Sri Lankan Rupee (LKR), Sri Lanka", "Bulgarian Lev (BGN), Bulgaria", "Croatian Kuna (HRK), Croatia", "Serbian Dinar (RSD), Serbia", "Tunisian Dinar (TND), Tunisia", "Ghanaian Cedi (GHS), Ghana", "Angolan Kwanza (AOA), Angola", "Macanese Pataca (MOP), Macau", "Uruguayan Peso (UYU), Uruguay", "Costa Rican Colón (CRC), Costa Rica", "Dominican Peso (DOP), Dominican Republic", "Icelandic Króna (ISK), Iceland", "Belarusian Rubles (BYN), Belarus", "Lebanese Pound (LBP), Lebanon", "Kazakhstani Tenge (KZT), Kazakhstan", "Uzbekistani Som (UZS), Uzbekistan", "Paraguayan Guarani (PYG), Paraguay", "Bolivian Boliviano (BOB), Bolivia", "Honduran Lempira (HNL), Honduras", "Guatemalan Quetzal (GTQ), Guatemala", "Jamaican Dollar (JMD), Jamaica", "Panamanian Balboa (PAB), Panama", "Fijian Dollar (FJD), Fiji", "Bahamian Dollar (BSD), Bahamas", "Barbadian Dollar (BBD), Barbados", "Trinidad and Tobago Dollar (TTD), Trinidad and Tobago", "East Caribbean Dollar (XCD), Eastern Caribbean", "Mauritian Rupee (MUR), Mauritius", "Botswana Pula (BWP), Botswana", "Namibian Dollar (NAD), Namibia", "Zambian Kwacha (ZMW), Zambia", "Maldivian Rufiyaa (MVR), Maldives", "Brunei Dollar (BND), Brunei", "Ethiopian Birr (ETB), Ethiopia", "Nepalese Rupee (NPR), Nepal", "Mongolian Tugrik (MNT), Mongolia", "Kyrgyzstani Som (KGS), Kyrgyzstan", "Tajikistani Somoni (TJS), Tajikistan", "Armenian Dram (AMD), Armenia", "Georgian Lari (GEL), Georgia", "Azerbaijani Manat (AZN), Azerbaijan", "Macedonian Denar (MKD), North Macedonia", "Albanian Lek (ALL), Albania", "Bosnian Convertible Mark (BAM), Bosnia and Herzegovina", "Moldovan Leu (MDL), Moldova", "CFA Franc BCEAO (XOF), West African States", "Pound Sterling (GBP), United Kingdom", "British Pound (GBP), United Kingdom", "New Taiwan Dollar (NTD), Taiwan", "n/a"]
        
    try:

        # Clean Unicode escapes
        json_output = validate_json_unicode(json_output)

        # Trim whitespace
        json_output = trim_json_whitespace(json_output)
        
        # Required fields
        required_fields = [
            "newsletter", "summary", "overview", "key_points", 
            "classification_weight", "organization", "event", "breakthrough",
            "financial_activity", "related_country"
        ]
        if not isinstance(json_output, dict) or not all(field in json_output for field in required_fields):
            missing_fields = [f for f in required_fields if f not in json_output]
            raise ValueError(f"JSON missing required fields: {', '.join(missing_fields)}")
        
        # Validate non-empty fields
        no_empty_fields = ["newsletter", "summary", "overview"]
        for field in no_empty_fields:
            if json_output[field] is None or (isinstance(json_output[field], str) and not json_output[field].strip()):
                raise ValueError(f"Field '{field}' cannot be empty")
        
        # Validate field types
        field_types = {
            "newsletter": str,
            "summary": str,
            "overview": str,
            "key_points": list,
            "classification_weight": dict,
            "organization": list,
            "event": list,
            "breakthrough": list,
            "financial_activity": list,
            "related_country": list
        }
        for field, expected_type in field_types.items():
            if not isinstance(json_output[field], expected_type):
                raise ValueError(f"'{field}' must be a {expected_type.__name__}")
        
        # Validate newsletter (5-10 words, 25-85 characters)
        newsletter_words = json_output["newsletter"].split()
        #if not (5 <= len(newsletter_words) <= 10):
        #    raise ValueError(f"newsletter must have 5-10 words, found {len(newsletter_words)}")
        if not (25 <= len(json_output["newsletter"]) <= 85):
            raise ValueError(f"newsletter must be 25-85 characters, found {len(json_output['newsletter'])}")
        
        # Validate summary (35-50 words, 250-400 characters)
        summary_words = json_output["summary"].split()
        #if not (35 <= len(summary_words) <= 50):
        #    raise ValueError(f"summary must have 35-50 words, found {len(summary_words)}")
        if not (250 <= len(json_output["summary"]) <= 400):
            raise ValueError(f"summary must be 250-400 characters, found {len(json_output['summary'])}")
        
        # Validate overview (150-250 words, 700-1500 characters)
        overview_words = json_output["overview"].split()
        #if not (150 <= len(overview_words) <= 250):
        #    raise ValueError(f"overview must have 150-250 words, found {len(overview_words)}")
        if not (700 <= len(json_output["overview"]) <= 1500):
            raise ValueError(f"overview must be 700-1500 characters, found {len(json_output['overview'])}")
        
        # Validate key_points (0-5 items)
        if len(json_output["key_points"]) > 5:
            raise ValueError(f"key_points must have 0-5 items, found {len(json_output['key_points'])}")
        for point in json_output["key_points"]:
            if not isinstance(point, str) or not point.strip():
                raise ValueError("key_points items must be non-empty strings")
        
        # Validate classification_weight
        json_output = validate_classification_weights(json_output, valid_classifications, max_weights)
                
        # Validate organization
        for org in json_output["organization"]:
            if not isinstance(org, dict):
                raise ValueError("Each organization must be a dict")
            if not all(k in org for k in ["name", "location"]):
                raise ValueError("Organization missing required fields: name, location")
            if not isinstance(org["name"], str) or len(org["name"]) < 3 or len(org["name"]) > 150:
                raise ValueError(f"Organization name must be 3-150 characters, found {len(org['name'])}")
            if not isinstance(org["location"], str) or len(org["location"]) < 3 or len(org["location"]) > 50:
                raise ValueError(f"Organization location must be 3-50 characters, found {len(org['location'])}")
                
            # Validate location format (City, Country; Country; or n/a)
            #if org["location"] != "n/a" and not re.match(r'^([A-Za-z\s]+,\s*[A-Za-z\s]+|[A-Za-z\s]+)(;([A-Za-z\s]+,\s*[A-Za-z\s]+|[A-Za-z\s]+))*$', org["location"]):
            #    raise ValueError(f"Invalid organization location format: {org['location']}")
        
        # Validate event
        
        for event in json_output["event"]:
            if not isinstance(event, dict):
                raise ValueError("Each event must be a dict")
            if not all(k in event for k in ["name", "location", "type", "description"]):
                raise ValueError("Event missing required fields: name, location, type, description")
            if not isinstance(event["name"], str) or not event["name"].strip():
                raise ValueError("Event name must be a non-empty string")
            if not isinstance(event["location"], str) or not event["location"].strip():
                raise ValueError("Event location must be a non-empty string")
            if event["type"] not in valid_event_types:
                raise ValueError(f"Invalid event type: {event['type']}")
            if not isinstance(event["description"], str) or not (150 <= len(event["description"]) <= 400):
                raise ValueError(f"Event description must be 150-400 characters, found {len(event['description'])}")
                
            # Validate location format (City, Country; Online, Global; or n/a)
            #if event["location"] not in ["n/a", "Online, Global"] and not re.match(r'^([A-Za-z\s]+,\s*[A-Za-z\s]+|Online,\s*Global)(;([A-Za-z\s]+,\s*[A-Za-z\s]+|Online,\s*Global))*$', event["location"]):
            #    raise ValueError(f"Invalid event location format: {event['location']}")
        
        # Validate breakthrough
        for breakthrough in json_output["breakthrough"]:
            if not isinstance(breakthrough, str) or not breakthrough.strip():
                raise ValueError("Breakthrough items must be non-empty strings")
        
        # Validate financial_activity        
        for activity in json_output["financial_activity"]:
            if not isinstance(activity, dict):
                raise ValueError("Each financial_activity must be a dict")
            if not all(k in activity for k in ["description", "currency"]):
                raise ValueError("Financial activity missing required fields: description, currency")
            if not isinstance(activity["description"], str) or not (150 <= len(activity["description"]) <= 400):
                raise ValueError(f"Financial activity description must be 150-400 characters, found {len(activity['description'])}")
            if activity["currency"] not in valid_currencies:
                raise ValueError(f"Invalid currency: {activity['currency']}")
        
        # Validate related_country (ISO 3166-1 alpha-3 codes)
        valid_countries = {"ABW", "AFG", "AGO", "AIA", "ALA", "ALB", "AND", "ARE", "ARG", "ARM", "ASM", "ATA", "ATF", "ATG", "AUS", "AUT", "AZE", 
                           "BDI", "BEL", "BEN", "BES", "BFA", "BGD", "BGR", "BHR", "BHS", "BIH", "BLM", "BLR", "BLZ", "BMU", "BOL", "BRA", "BRB", 
                           "BRN", "BTN", "BVT", "BWA", "CAF", "CAN", "CCK", "CHE", "CHL", "CHN", "CIV", "CMR", "COD", "COG", "COK", "COL", "COM", 
                           "CPV", "CRI", "CUB", "CUW", "CXR", "CYM", "CYP", "CZE", "DEU", "DJI", "DMA", "DNK", "DOM", "DZA", "ECU", "EGY", "ERI", 
                           "ESH", "ESP", "EST", "ETH", "FIN", "FJI", "FLK", "FRA", "FRO", "FSM", "GAB", "GBR", "GEO", "GGY", "GHA", "GIB", "GIN", 
                           "GLP", "GMB", "GNB", "GNQ", "GRC", "GRD", "GRL", "GTM", "GUF", "GUM", "GUY", "HKG", "HMD", "HND", "HRV", "HTI", "HUN", 
                           "IDN", "IMN", "IND", "IOT", "IRL", "IRN", "IRQ", "ISL", "ISR", "ITA", "JAM", "JEY", "JOR", "JPN", "KAZ", "KEN", "KGZ", 
                           "KHM", "KIR", "KNA", "KOR", "KWT", "LAO", "LBN", "LBR", "LBY", "LCA", "LIE", "LKA", "LSO", "LTU", "LUX", "LVA", "MAC", 
                           "MAF", "MAR", "MCO", "MDA", "MDG", "MDV", "MEX", "MHL", "MKD", "MLI", "MLT", "MMR", "MNE", "MNG", "MNP", "MOZ", "MRT", 
                           "MSR", "MTQ", "MUS", "MWI", "MYS", "MYT", "NAM", "NCL", "NER", "NFK", "NGA", "NIC", "NIU", "NLD", "NOR", "NPL", "NRU", 
                           "NZL", "OMN", "PAK", "PAN", "PCN", "PER", "PHL", "PLW", "PNG", "POL", "PRI", "PRK", "PRT", "PRY", "PSE", "PYF", "QAT", 
                           "REU", "ROU", "RUS", "RWA", "SAU", "SDN", "SEN", "SGP", "SGS", "SHN", "SJM", "SLB", "SLE", "SLV", "SMR", "SOM", "SPM", 
                           "SRB", "SSD", "STP", "SUR", "SVK", "SVN", "SWE", "SWZ", "SXM", "SYC", "SYR", "TCA", "TCD", "TGO", "THA", "TJK", "TKL", 
                           "TKM", "TLS", "TON", "TTO", "TUN", "TUR", "TUV", "TWN", "TZA", "UGA", "UKR", "UMI", "URY", "USA", "UZB", "VAT", "VCT", 
                           "VEN", "VGB", "VIR", "VNM", "VUT", "WLF", "WSM", "YEM", "ZAF", "ZMB", "ZWE", "NTD"
        }
        
        for country in json_output["related_country"]:
            if not isinstance(country, str) or country not in valid_countries:
                raise ValueError(f"Invalid country code: {country}")
        
        return json_output, True
    
    except (json.JSONDecodeError, ValueError) as e:
        
        logger.warning(f"Invalid JSON for {article_hash}: {e}")
        
        if debug:
            logger.debug(f"Failed JSON: {json_output}")

        return json_output, str(e)
    
def generate_content_json(model, article_hash, language, debug=False, max_retries=10):
    """
    Process a text file with a language model to generate a JSON file.
    
    Args:
        model: Initialized language model (e.g., from LM Studio).
        article_hash (str): Unique hash for the article (e.g., SHA256 of URL).
        language (str): Language for validation ('en' or 'ptbr').
        debug (bool): Enable debug logging.
        max_retries (int): Maximum retries for model inference.
    
    Returns:
        str: None if failed.
    """

    try:
        
        output_file = os.path.join(PARSE_DIR, f"{article_hash}_{language}.json")
        output_file_error = os.path.join(PARSE_DIR, f"error_{article_hash}_{language}.json")
        
        if os.path.exists(output_file) and LLM_RERUN == False:
            logger.info(f"Skip run: keep existing Content JSON [{language}] {article_hash}")
            return None      

        if language == 'en':
            
            content_file = os.path.join(CONTENT_DIR, f"{article_hash}.txt")

            if not content_file or not os.path.exists(content_file):
                logger.warning(f"No valid content file provided, skipping JSON generation {article_hash}")
                return None        
    
            with open(content_file, "r", encoding="utf-8") as f:
                content = f.read()
                
            logger.info(f"Processing {article_hash} (content length: {len(content)} characters)")
            
            sanitized_content = sanitize_content(content)
            
            if len(sanitized_content) != len(content):
                logger.warning(f"Content sanitized for {article_hash}: original length {len(content)}, sanitized length {len(sanitized_content)}")
            if debug:
                input_copy_file = os.path.join(PARSE_DIR, f"debug_{article_hash}.txt")
                with open(input_copy_file, "w", encoding="utf-8") as f:
                    f.write(sanitized_content)
                logger.info(f"Saved input content to {input_copy_file}")
            if len(sanitized_content) > LLM_MAX_INPUT_LENGHT:
                logger.warning(f"Input too long for {article_hash} ({len(sanitized_content)} chars), truncating to {LLM_MAX_INPUT_LENGHT}")
                truncated = sanitized_content[:LLM_MAX_INPUT_LENGHT]
                last_period = truncated.rfind('.')
                if last_period > 0:
                    sanitized_content = truncated[:last_period + 1]
                else:
                    sanitized_content = truncated
                if debug:
                    logger.debug(f"Truncated content length: {len(sanitized_content)}")
                    
            prompt = LLM_PARSE_PROMPT_PTBR.replace("{content}", sanitized_content)
        
        else:
            
            content_file = os.path.join(PARSE_DIR, f"{article_hash}_en.json")

            if not content_file or not os.path.exists(content_file):
                logger.warning(f"No valid parse file provided, skipping JSON translation")
                return None        
    
            with open(content_file, "r", encoding="utf-8") as f:
                content = f.read()
                
            logger.info(f"Translating {article_hash} (content length: {len(content)} characters)")
                    
            prompt = LLM_TRANSLATE_PROMPT_PTBR.replace("{content}", content)            

        logger.info(f"Final prompt {article_hash} (content length: {len(prompt)} characters)")
        
        if debug:
            logger.debug(f"Prepared prompt for {article_hash}: {prompt[:500]}...")
            
        for attempt in range(max_retries):
            try:
                logger.info(f"Sending prompt for {article_hash} (attempt {attempt+1}/{max_retries})")
                
                if language == 'en':                  
                    result = model.respond(prompt, config = LLM_CONFIG, response_format = LLM_PARSE_SCHEMA)
                
                else:                 
                    result = model.respond(prompt, config = LLM_CONFIG, response_format = LLM_TRANSLATE_SCHEMA_PTBR)                   

                if debug:
                    logger.debug(f"Prediction Result attributes: {dir(result)}")
                output_text = result.content.strip() if hasattr(result, 'content') else str(result).strip()
                if debug:
                    logger.debug(f"Raw model response for {article_hash}: {output_text}")
                    raw_output_file = os.path.join(PARSE_DIR, f"debug_{content_file}_raw.txt")
                    with open(raw_output_file, "w", encoding="utf-8") as f:
                        f.write(output_text)
                    logger.info(f"Saved raw response to {raw_output_file}")
                json_output = extract_json_from_response(output_text)
                if not json_output:
                    logger.warning(f"No JSON detected in response for {article_hash}")
                    if attempt < max_retries - 1:
                        logger.info(f"Retrying {article_hash}: {attempt+1}")
                        time.sleep(1)
                        continue
                    raise ValueError("No valid JSON found in response")              

                json_output, json_flag = validate_json_structure(json_output, article_hash, language, debug) 

                if json_flag != True:                  

                    if attempt < max_retries - 1:
                        logger.info(f"Retrying {article_hash} due to validation error: {json_flag}")
                        time.sleep(1)
                        continue
                    
                    logger.error(f"Failed to parse JSON for {article_hash} after {max_retries} attempts")
                    json_output = {"error": json_flag, "raw_output": output_text}                   
          
                with open(output_file, "w", encoding="utf-8") as f:
                    json.dump(json_output, f, indent=2, ensure_ascii=False)
                logger.info(f"Saved parsed output to {output_file}")
                if debug:
                    logger.debug(f"Model used: {result.model_info.display_name}")
                    logger.debug(f"Predicted tokens: {result.stats.predicted_tokens_count}")
                    logger.debug(f"Time to first token (seconds): {result.stats.time_to_first_token_sec}")
                    logger.debug(f"Stop reason: {result.stats.stop_reason}")
                return output_file
            except lms.LMStudioError as e:
                logger.error(f"Model inference failed for {article_hash} (attempt {attempt+1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    logger.info(f"Retrying {article_hash}: {attempt+1}")
                    time.sleep(1)
                    continue
                logger.error(f"Model inference failed for {article_hash} after {max_retries} attempts")
                json_output = {"error": str(e), "raw_output": output_text if 'output_text' in locals() else "No response"}

                with open(output_file_error, "w", encoding="utf-8") as f:
                    json.dump(json_output, f, indent=2, ensure_ascii=False)
                logger.info(f"Saved error output to {output_file}")
                return output_file
    except Exception as e:
        logger.error(f"Error processing {article_hash}: {e}")
        if debug:
            logger.error(f"Traceback: {traceback.format_exc()}")
        json_output = {"error": str(e)}
        if debug:
            json_output["traceback"] = traceback.format_exc()

        with open(output_file_error, "w", encoding="utf-8") as f:
            json.dump(json_output, f, indent=2, ensure_ascii=False)
        logger.info(f"Saved error output to {output_file}")
        return output_file 
    
def load_existing_articles(articles_dict, output_file='quantum_articles.json'):
    """
    Load existing articles from JSON file into articles_dict.
    
    Args:
        articles_dict (dict): Dictionary to store articles.
        output_file (str): Path to articles JSON file.
    """
    if os.path.exists(output_file):
        try:
            with open(output_file, 'r', encoding='utf-8') as f:
                articles = json.load(f)
                if not isinstance(articles, list) or not articles:
                    logger.warning(f"{output_file} is empty or invalid, initializing empty articles")
                    return
                for article in articles:
                    articles_dict[article['url']] = article
                logger.info(f"Loaded {len(articles)} existing articles")
        except (json.JSONDecodeError, KeyError) as e:
            logger.warning(f"Invalid {output_file}: {e}, initializing empty articles")
    else:
        logger.info(f"No {output_file} found, starting fresh")

def save_articles(articles_dict, sort_order='desc', output_file='quantum_articles.json'):
    """
    Save articles to JSON file, sorted by timestamp.
    
    Args:
        articles_dict (dict): Dictionary of articles.
        sort_order (str): 'asc' or 'desc' for sorting.
        output_file (str): Path to output JSON file.
    """
    articles_list = list(articles_dict.values())
    if sort_order:
        logger.info(f"Sorting articles by published ({sort_order})")
        articles_list.sort(
            key=lambda x: x['published'] or '9999-12-31T00:00:00',
            reverse=(sort_order == 'desc')
        )
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(articles_list, f, indent=4, ensure_ascii=False)
    logger.info(f"Saved {len(articles_list)} articles to {output_file}")
    
def merge_json_files(article_file_path, language, parse_dir_path, output_file_path):
    # Ensure parse directory exists
    parse_dir = Path(parse_dir_path)
    if not parse_dir.exists():
        raise FileNotFoundError(f"Parse directory {parse_dir_path} does not exist")

    # Read the main article.json file
    try:
        with open(article_file_path, 'r', encoding='utf-8') as f:
            articles = json.load(f)
    except FileNotFoundError:
        raise FileNotFoundError(f"Article file {article_file_path} not found")
    except json.JSONDecodeError:
        raise ValueError(f"Invalid JSON in {article_file_path}")

    # Process each article
    for article in articles:
        hash_value = article.get('hash')
        if not hash_value:
            print(f"Warning: Article missing hash value: {article.get('title', 'Unknown')}")
            continue

        # Construct path to hash-specific JSON file
        hash_file_path = parse_dir / f"{hash_value}_{language}.json"

        # Check if hash file exists
        if not hash_file_path.exists():
            print(f"Warning: No parse file found for hash {hash_value} at {hash_file_path}")
            continue

        # Read and merge the hash-specific JSON file
        try:
            with open(hash_file_path, 'r', encoding='utf-8') as f:
                parse_data = json.load(f)
                # Merge parse_data into article
                article.update(parse_data)
        except json.JSONDecodeError:
            print(f"Warning: Invalid JSON in {hash_file_path}")
        except Exception as e:
            print(f"Error processing {hash_file_path}: {str(e)}")

    # Save the merged data to output file
    try:
        with open(output_file_path, 'w', encoding='utf-8') as f:
            json.dump(articles, f, indent=4, ensure_ascii=False)
        print(f"Merged data saved to {output_file_path}")
    except Exception as e:
        raise Exception(f"Failed to save output file: {str(e)}")