# thequantuminsider.py
import os
import json
import logging
import hashlib
from datetime import datetime
import html
from bs4 import BeautifulSoup
from json_repair import repair_json
import re
from core.utils import (
    get_cached_page, parse_article_date, ensure_directories,
    ARTICLE_DIR, CACHE_DIR, HTML_TEMPLATE,
    get_cache_file_name, initialize_driver, 
    logger, generate_content_text, generate_content_json,
    remove_dupes, sortbydate, is_after_min_date,
    extract_article_metadata
)

#################

def qz_extract_metadata(soup):
    """
    Extract normalized metadata for a Quantum Zeitgeist article page.

    The schema graph is located by @type (the site currently places its
    NewsArticle node at index 7, but the order is not stable).

    Args:
        soup (BeautifulSoup): Parsed article page.

    Returns:
        dict | None: Metadata, or None when the page declares none.
    """
    metadata = extract_article_metadata(soup, script_class='rank-math-schema-pro')

    if metadata is None:
        return None

    tags = soup.find('div', class_='tags-section')

    if tags:
        metadata['keywords'] = [
            tag.get_text() for tag in tags.find_all('a') if tag.get_text(strip=True)
        ]

    return metadata

def qz_is_relevant(metadata):
    """
    Decide whether an article belongs in a quantum newsletter.

    Args:
        metadata (dict): Metadata from qz_extract_metadata.

    Returns:
        bool: True when 'quantum' appears in categories, title or keywords.
    """
    haystack = ' '.join(
        list(metadata.get('category') or [])
        + [metadata.get('title') or '']
        + list(metadata.get('keywords') or [])
    ).lower()

    return 'quantum' in haystack

def qz_scrape_sitemap(list_sitemap, ignore_cache, driver, debug=False):
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

def qz_generate_article_html(url, articles_dict, ignore_cache, driver, debug=False):
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
    
    post_content = soup.find('article', class_='post')
    
    if not post_content:
    
        logger.warning(f"No article found for {url}")
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

        metadata = qz_extract_metadata(soup)
        
        if metadata is None:
            logger.warning(f"No metadata found within article for {url}")
            return None

        if not qz_is_relevant(metadata):
            logger.warning(f"Category invalid found within article for {url}")
            return None

        article_data.update(metadata)

        content_container = post_content.find('div', class_='entry-content')
        
        if not content_container:
            logger.warning(f"No entry-content found within article for {url}")            
            return None

        else:

            content_soup = content_container
                
            for img in content_soup.find_all('img'):
                img.decompose()
                
            for svg in content_soup.find_all('svg'):
                svg.decompose()
                
            for tag in content_soup.find_all(['p', 'div', 'span']):
                if not tag.get_text(strip=True) and not tag.find_all(['a', 'strong', 'em']):
                    tag.decompose()
            for tag in content_soup.find_all(True):
                if tag.name == 'a':
                    href = tag.get('href')
                    tag.attrs = {'href': href} if href else {}
                else:
                    tag.attrs = {}
                    
            for div in content_soup.find_all('div'):
                div.decompose()
                    
            content_html = []
            
            for p in content_soup.find_all('p'):  
                content_html.append('<p>' + p.get_text().strip() + '</p>')            
            
            content_html = ''.join(content_html)                         
           
            #content_html = ''.join(str(child) for child in content_soup.contents)

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
                'source': 'Quantum Zeitgeist'                    
            }
            
            articles_dict[url] = article_dict
            
            return article_dict
              
def quantumzeitgeist(model, articles_dict, ignore_cache=False, debug=False,
                     min_date=None, filter_by_sitemap_date=False, should_cancel=None):
    
    driver = initialize_driver()
    
    try:

        # https://quantumzeitgeist.com/sitemap_index.xml
        list_sitemap = []
        
        for k in range(1, 60):
            list_sitemap.append('https://quantumzeitgeist.com/post-sitemap' + str(k) + '.xml')      
        
        url_list = qz_scrape_sitemap(list_sitemap, ignore_cache, driver, debug)

        if filter_by_sitemap_date and min_date:
            url_list = [item for item in url_list if is_after_min_date(item['date'], min_date)]

        number_urls = len(url_list)
        
        logger.info(f"Number of urls identified: {number_urls}")
        
        #url_list =[{'url':'https://quantumzeitgeist.com/photonic-chip-demonstrates-quantum-teleportation-of-qubit-for-modular-quantum-computing/'}]
        
        ignore_urls = ['https://quantumzeitgeist.com/nvidia-wins-neurips-awards/']
        
        i = 0
        
        for article_data in url_list:

            i = i + 1
            
            logger.warning(f"Current URL: {i} / {number_urls}")

            article_url = article_data['url'] 
            
            if should_cancel is not None and should_cancel():
                logger.warning("Cancelamento solicitado pelo usuário. Interrompendo portal.")
                break
            
            if article_url in ignore_urls:
                continue
                          
            article_hash = hashlib.sha256(article_url.encode()).hexdigest()
            
            # Generate HTML        
            article_dict = qz_generate_article_html(article_url, articles_dict, ignore_cache, driver, debug)
            
            if article_dict == None:
                logger.warning(f"Skip due to invalid article dict!")
                continue
            
            if not is_after_min_date(article_dict.get('published'), min_date):
                logger.warning(f"Skip due to published date ({article_dict.get('published')})!")
                continue
            
            # Generate TXT
            generate_content_text(article_hash, debug=debug)
            
            # Generate JSON
            generate_content_json(model, article_hash, 'en', debug=debug)   
                
    finally:
        driver.quit()
        logger.info("WebDriver closed for quantumzeitgeist")