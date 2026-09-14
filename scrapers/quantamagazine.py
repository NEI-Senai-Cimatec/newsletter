# thequantuminsider.py
import os
import json
import logging
import hashlib
from datetime import datetime
import html
from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning
import re
from utils import (
    get_cached_page, parse_article_date, ensure_directories,
    ARTICLE_DIR, CACHE_DIR, HTML_TEMPLATE,
    get_cache_file_name, initialize_driver, 
    logger, generate_content_text, generate_content_json,
    remove_dupes, sortbydate
)

#################

def qm_scrape_sitemap(list_sitemap, ignore_cache, driver, debug=False):
    """
    Scrape multiple sitemaps and extract URLs and dates.
    
    Args:
        list_sitemap (array): List of sitemap URLs
        ignore_cache (bool): Whether to ignore cached pages
        driver: Web driver instance
        debug (bool): Debug mode flag
        
    Returns:
        list: Sorted list of dictionaries containing URLs and dates
    """
    
    sitemap_data = []
    
    for sitemap_url in list_sitemap:
        try:
            # Get page content using cached or fresh fetch
            page_source = get_cached_page(sitemap_url, ignore_cache, driver, type_='sitemap')
            
            # Parse XML content
            soup = BeautifulSoup(page_source, features="xml")
            
            # Find all URL entries
            for entry in soup.find_all('url'):
                    
                article = {}
                
                # Extract URL
                article['url'] = entry.find('loc').text

                if '/videos/' in article['url'] or '/quantanews/' in article['url']:
                    continue
                
                # Extract last modified date
                article['date'] = entry.find('lastmod').text

                # Convert date to match provided format (e.g., '2025-08-13 15:44 +00:00')
                try:
                    parsed_date = datetime.fromisoformat(article['date'])
                    article['date'] = parsed_date.strftime('%Y-%m-%d %H:%M %z')

                except (ValueError, KeyError):
                    logger.warning(f"Invalid date format for {article['url']}: {article['date']}")
                    continue
                    
                sitemap_data.append(article)
                
                if debug:
                    logger.debug(f"Processed article: {article}")
                    
        except Exception as e:
            logger.error(f"Error processing sitemap {sitemap_url}: {str(e)}")
            continue
    
    # Sort the collected data by date
    sitemap_data = remove_dupes(sitemap_data)
    sitemap_data = sortbydate(sitemap_data)
    
    if debug:
        logger.debug(f"Total articles collected: {len(sitemap_data)}")
    
    return sitemap_data

def qm_generate_article_html(url, articles_dict, ignore_cache, driver, debug=False):
    """
    Fetch and parse an article page, extract content, and generate an HTML file.
    
    Args:
        url (str): Article URL.
        ignore_cache (bool): Ignore cache and fetch fresh page.
        driver: Selenium WebDriver instance.
        debug (bool): Enable debug logging.
    """
    
    article_data = {}
    
    article_data['title'] = ''
    article_data['author'] = ''
    article_data['article_date'] = ''
    article_data['category'] = []    
        
    article_hash = hashlib.sha256(url.encode()).hexdigest()
    article_file = os.path.join(ARTICLE_DIR, f"{article_hash}.html")
        
    if os.path.exists(article_file):
        logger.info(f"Skip run: keep existing Article HTML")
        return articles_dict[url] if (url in articles_dict) else None   
        
    page_source = get_cached_page(url, ignore_cache, driver, type_='article')
    page_source = html.unescape(page_source)
    soup = BeautifulSoup(page_source, 'html.parser')
    
    post_content = soup.find_all('div', class_='post__content')
    
    if not post_content:
    
        logger.warning(f"No post__content found for {url}")
        if debug:
            debug_file = os.path.join(CACHE_DIR, f"{get_cache_file_name(url, 'article')}_no_content.html")
            with open(debug_file, 'w', encoding='utf-8') as f:
                f.write(page_source)
            logger.debug(f"Saved page source for debugging to {debug_file}")
        content_html = "<p>No content available.</p>"

    else:
            
        article_data = {}
        
        article_data['title'] = ''
        article_data['author'] = ''
        article_data['dateModified'] = ''
        article_data['datePublished'] = ''
        article_data['category'] = []  
        article_data['keywords'] = []        

        for script_data in soup.find_all('script'):
        
            if '@graph' in script_data.text:
                metadata = script_data.text
                metadata = json.loads(metadata)
            
            if 'ga4Array' in script_data.text:
                metadata_2 = script_data.text[25:-7]
                metadata_2 = json.loads(metadata_2)
        
        if metadata_2['kicker'] == None or 'quantum' not in metadata_2['kicker'].split(' '):
            logger.warning(f"Category invalid found within article for {url}")
            return None
            
        article_data['category'] = metadata_2['category']

        article_data['title'] = metadata['@graph'][1]['name'][0:-18] if 'name' in metadata['@graph'][1] else ''           
        article_data['author'] = metadata['@graph'][1]['author']['name'] if 'author' in metadata['@graph'][1] else '' 
        article_data['date'] = parse_article_date(metadata['@graph'][1]['datePublished'])[0] if 'datePublished' in metadata['@graph'][1] else '' 
        article_data['datePublished'] = parse_article_date(metadata['@graph'][1]['datePublished'])[1] if 'datePublished' in metadata['@graph'][1] else ''  
        article_data['dateModified'] = parse_article_date(metadata['@graph'][1]['dateModified'])[1] if 'dateModified' in metadata['@graph'][1] else ''  

        for entry in soup.find('div', class_='sidebar__tag-wrap').find_all('span', class_='theme__text'):
            
            article_data['keywords'].append(entry.text)
  
        content_html = []
        
        for section_data in post_content[1:]:
            
            for ul in section_data.find_all('ul', class_='wp-block-list'):
                ul.decompose()
                
            for img in section_data.find_all('img'):
                img.decompose()
                
            for svg in section_data.find_all('svg'):
                svg.decompose()
                
            for aside in section_data.find_all('aside'):
                aside.decompose()            

            for tag in section_data.find_all(['p', 'div', 'span']):
                if not tag.get_text(strip=True) and not tag.find_all(['a', 'strong', 'em']):
                    tag.decompose()
                    
            for tag in section_data.find_all(True):
                if tag.name == 'a':
                    href = tag.get('href')
                    tag.attrs = {'href': href} if href else {}
                else:
                    tag.attrs = {}
                    
            for p in section_data.find_all('p'):  
                content_html.append('<p>' + p.get_text().strip() + '</p>')            
            
        content_html = ''.join(content_html)            
        
        html_content = HTML_TEMPLATE.format(
            title=article_data['title'],
            author=article_data['author'],
            article_date=article_data['date'],
            article_published=article_data['datePublished'],
            article_modified=article_data['dateModified'],
            categories=', '.join(article_data['category']),
            keywords=', '.join(article_data['keywords']),
            url=url,
            content_html=content_html
        )
        
        with open(article_file, 'w', encoding='utf-8') as f:
            f.write(html_content)
        logger.info(f"Generated article HTML: {article_file}")

        if url in articles_dict:         
            del articles_dict[url]
            logger.info(f"Updated article: {url}")
        else:
            logger.info(f"Added new article: {url}")
            
        article_dict = {
            'url': url,
            'title': article_data['title'],
            'category': article_data['category'],
            'author': article_data['author'],
            'date': article_data['date'],
            'published': article_data['datePublished'],
            'modified': article_data['dateModified'],
            'timestamp': datetime.now().isoformat(),
            'keywords': article_data['keywords'],
            'hash': article_hash,
            'source': 'Quanta Magazine'                    
        }
        
        articles_dict[url] = article_dict
        
        return article_dict

def quantamagazine(model, articles_dict, ignore_cache=False, debug=False):
    
    driver = initialize_driver()
    
    try:

        list_sitemap = [
            'https://www.quantamagazine.org/sitemap_index.xml'
        ]         
        
        url_list = qm_scrape_sitemap(list_sitemap, ignore_cache, driver, debug)
        
        number_urls = len(url_list)
        
        logger.info(f"Number of urls identified: {number_urls}")
        
        ignore_urls = ['https://www.quantamagazine.org/',
                       'https://www.quantamagazine.org/archive/',
                       'https://www.quantamagazine.org/podcasts/',
                       'https://www.quantamagazine.org/homepage-test/',
                       'https://www.quantamagazine.org/topics/',
                       'https://www.quantamagazine.org/gift-store/',
                       'https://www.quantamagazine.org/saved-articles/',
                       'https://www.quantamagazine.org/terms-conditions/',
                       'https://www.quantamagazine.org/privacy-policy/',
                       'https://www.quantamagazine.org/contact-us/',
                       'https://www.quantamagazine.org/about/',
                       'https://www.quantamagazine.org/videos/',
                       'https://www.quantamagazine.org/cloudflare-blocked/',
                       'https://www.quantamagazine.org/posts-for-simons-homepage/',
                       'https://www.quantamagazine.org/ai-editorial-policy/']
        
        i = 0
        
        for article_data in url_list:

            i = i + 1
            
            logger.warning(f"Current URL: {i} / {number_urls}")
            
            article_url = article_data['url'] 
            
            if article_url in ignore_urls:
                continue

            article_hash = hashlib.sha256(article_url.encode()).hexdigest()
            
            # Generate HTML        
            article_dict = qm_generate_article_html(article_url, articles_dict, ignore_cache, driver, debug)
            
            if article_dict == None:
               logger.warning(f"Skip due to invalid article dict!")
               continue
            
            if '2025-10' not in article_dict['published']:
                logger.warning(f"Skip due to published date!")
                continue
            
            # Generate TXT
            generate_content_text(article_hash, debug=debug)
            
            # Generate JSON
            generate_content_json(model, article_hash, 'en', debug=debug)    
                
    finally:
        driver.quit()
        logger.info("WebDriver closed for quantamagazine")