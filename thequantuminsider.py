# thequantuminsider.py
import os
import json
import logging
import hashlib
from datetime import datetime
import html
from bs4 import BeautifulSoup
import re
from utils import (
    get_cached_page, parse_article_date, ensure_directories,
    ARTICLE_DIR, CACHE_DIR, HTML_TEMPLATE,
    get_cache_file_name, initialize_driver, 
    logger, generate_content_text, generate_content_json,
    remove_dupes, sortbydate
)

#################

def tqi_scrape_sitemap(list_sitemap, ignore_cache, driver, debug=False):
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
                    
            # # Parse XML content
            # soup = BeautifulSoup(page_source, 'html.parser')
            
            # table = soup.find('tbody')
            
            # # Find all URL entries
            # for entry in table.find_all('tr'):
                
            #     entry_data = entry.find_all('td')
                    
            #     article = {}
                
            #     # Extract URL
            #     article['url'] = entry_data[0].find('a')['href']
                
            #     # Extract last modified date
            #     article['date'] = entry_data[2].text

            #     # Convert date to match provided format (e.g., '2025-08-13 15:44 +00:00')
            #     try:
            #         parsed_date = datetime.fromisoformat(article['date'].replace('Z', '+00:00'))
            #         article['date'] = parsed_date.strftime('%Y-%m-%d %H:%M %z')

            #     except (ValueError, KeyError):
            #         logger.warning(f"Invalid date format for {article['url']}: {article['date']}")
            #         continue
                    
            #     sitemap_data.append(article)
                
            #     if debug:
            #         logger.debug(f"Processed article: {article}")
                    
        except Exception as e:
            logger.error(f"Error processing sitemap {sitemap_url}: {str(e)}")
            continue
    
    # Sort the collected data by date
    sitemap_data = remove_dupes(sitemap_data)
    sitemap_data = sortbydate(sitemap_data)
    
    if debug:
        logger.debug(f"Total articles collected: {len(sitemap_data)}")
    
    return sitemap_data

def tqi_generate_article_html(url, articles_dict, ignore_cache, driver, debug=False):
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
    
    post_content = soup.find('div', class_='elementor-widget-theme-post-content')
    
    if not post_content:
    
        logger.warning(f"No elementor-widget-theme-post-content found for {url}")
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

        metadata = soup.find('script', class_='yoast-schema-graph')
        
        if metadata:
            
            metadata = json.loads(metadata.text)
    
            article_data['title'] = metadata['@graph'][0]['headline'] if 'headline' in metadata['@graph'][0] else '' 
            article_data['author'] = metadata['@graph'][0]['author']['name'] if 'author' in metadata['@graph'][0] else '' 
            article_data['date'] = parse_article_date(metadata['@graph'][0]['datePublished'])[0] if 'datePublished' in metadata['@graph'][0] else '' 
            article_data['datePublished'] = parse_article_date(metadata['@graph'][0]['datePublished'])[1] if 'datePublished' in metadata['@graph'][0] else ''  
            article_data['dateModified'] = parse_article_date(metadata['@graph'][0]['dateModified'])[1] if 'dateModified' in metadata['@graph'][0] else ''  
            article_data['category'] = metadata['@graph'][0]['articleSection'] if 'articleSection' in metadata['@graph'][0] else '' 
            article_data['keywords'] = metadata['@graph'][0]['keywords'] if 'keywords' in metadata['@graph'][0] else ''
            
        else:
            
            metadata = soup.find_all('script', attrs={'type': 'application/ld+json'})
            
            metadata = json.loads(metadata[1].text)

            article_data['title'] = metadata['headline'] if 'headline' in metadata else '' 
            article_data['author'] = metadata['author']['name'] if 'author' in metadata else '' 
            article_data['date'] = parse_article_date(metadata['datePublished'])[0] if 'datePublished' in metadata else '' 
            article_data['datePublished'] = parse_article_date(metadata['datePublished'])[1] if 'datePublished' in metadata else '' 
            article_data['dateModified'] = parse_article_date(metadata['dateModified'])[1] if 'dateModified' in metadata else '' 
            article_data['category'] = [metadata['articleSection']] if 'articleSection' in metadata else '' 
            article_data['keywords'] = metadata['keywords'] if 'keywords' in metadata else ''   
                
        content_container = post_content.find('div', class_='elementor-widget-container')
        
        if not content_container:
            logger.warning(f"No elementor-widget-container found within elementor-widget-theme-post-content for {url}")
            
            return None

        else:

            content_soup = content_container
            
            for ul in content_soup.find_all('ul', class_='wp-block-list'):
                ul.decompose()
            for p in content_soup.find_all('p'):
                strong = p.find('strong')
                if strong and 'Insider Brief' in strong.text.strip():
                    p.decompose()
            for toc in content_soup.find_all(['div', 'nav'], class_=lambda x: x and 'ez-toc' in x):
                toc.decompose()
            for nav in content_soup.find_all('nav'):
                nav.decompose()
            for figure in content_soup.find_all('figure'):
                figure.decompose()
            for img in content_soup.find_all('img'):
                img.decompose()
            for noscript in content_soup.find_all('noscript'):
                noscript.decompose()
            for picture in content_soup.find_all('picture'):
                picture.decompose()
            for a in content_soup.find_all('a'):
                if (a.get('class') and 'responsive-image' in a.get('class')) or \
                   a.find(['picture', 'source', 'img']) or \
                   not a.get_text(strip=True):
                    a.decompose()
            for tag in content_soup.find_all(['p', 'div', 'span']):
                if not tag.get_text(strip=True) and not tag.find_all(['a', 'strong', 'em']):
                    tag.decompose()
            for tag in content_soup.find_all(True):
                if tag.name == 'a':
                    href = tag.get('href')
                    tag.attrs = {'href': href} if href else {}
                else:
                    tag.attrs = {}
                    
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
                'source': 'The Quantum Insider'                    
            }
            
            articles_dict[url] = article_dict
            
            return article_dict
              
def thequantuminsider(model, articles_dict, ignore_cache=False, debug=False):
    
    driver = initialize_driver()
    
    try:

        # https://thequantuminsider.com/sitemap_index.xml
        list_sitemap = []
        
        list_sitemap.append('https://thequantuminsider.com/post-sitemap.xml') 
        
        for k in range(2, 9):
            list_sitemap.append('https://thequantuminsider.com/post-sitemap' + str(k) + '.xml')          
              
        url_list = tqi_scrape_sitemap(list_sitemap, ignore_cache, driver, debug)
        
        number_urls = len(url_list)
        
        logger.info(f"Number of urls identified: {number_urls}")
        
        ignore_urls = ['https://thequantuminsider.com/2025/03/05/space-based-quantum-key-distribution-a-deep-dive-into-qkds-market-map-and-competitive-landscape',
                       'https://thequantuminsider.com/2023/12/14/improved-performance-of-superconducting-qubits-makes-investigation-of-sapphire-substrates-compelling-as-an-alternative-to-silicon/',
                       'https://thequantuminsider.com/2019/07/30/move-over-qubit-theres-a-new-q-in-town-the-qudit/',
                       'https://thequantuminsider.com/2024/07/13/superposition-guys-podcast-quantum-at-keysight-technologies/',
                       'https://thequantuminsider.com/2021/07/28/leading-experts-urge-applying-the-power-of-quantum-technology-to-sustainability-in-new-documentary-our-sustainable-future/',
                       'https://thequantuminsider.com/solutions/#new_tab',
                       'https://thequantuminsider.com/data/#new_tab']
        
        i = 0
        
        for article_data in url_list:

            i = i + 1
            
            logger.warning(f"Current URL: {i} / {number_urls}")

            article_url = article_data['url'] 
            
            if article_url in ignore_urls:
                continue
            
            # if 'https://thequantuminsider.com/2025/' not in article_url:
            #     continue
                          
            article_hash = hashlib.sha256(article_url.encode()).hexdigest()
            
            # Generate HTML        
            article_dict = tqi_generate_article_html(article_url, articles_dict, ignore_cache, driver, debug)
            
            if article_dict == None:
               logger.warning(f"Skip due to invalid article dict!")
               continue
            
            # if '2026-01' not in article_dict['published']:
            #    logger.warning(f"Skip due to published date!")
            #    continue
           
            if '2026-06' in article_dict['published']:
                
                # Generate TXT
                generate_content_text(article_hash, debug=debug)
                    
                # Generate JSON
                generate_content_json(model, article_hash, 'en', debug=debug)  
                
            else:
                
               logger.warning(f"Skip due to published date!")
               continue 
                
    finally:
        driver.quit()
        logger.info("WebDriver closed for thequantuminsider")