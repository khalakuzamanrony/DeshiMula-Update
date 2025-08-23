import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import time
import json

# Configuration
BASE_URL = "https://deshimula.com/"
TELEGRAM_TOKEN = "8496239540:AAG-S0RR1ReXY349kR3TdOjB5gCHAHNbNnU"
CHAT_ID = "6893240036"
OUTPUT_FILE = "all_posts.json"

def log(msg):
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}")

def get_page_posts(page_url):
    """Get posts from a single page"""
    try:
        response = requests.get(page_url)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        posts = []
        post_containers = soup.find_all('div', class_='container mt-5')
        
        for container in post_containers:
            title_elem = container.find('div', class_='post-title')
            title = title_elem.text.strip() if title_elem else "No title"
            
            link_elem = container.find('a', class_='hyper-link')
            link = urljoin(BASE_URL, link_elem['href']) if link_elem else "No link"
            
            company_elem = container.find('span', class_='company-name')
            company = company_elem.text.strip() if company_elem else "Unknown"
            
            role_elem = container.find('span', class_='reviewer-role')
            role = role_elem.text.strip() if role_elem else "Unknown"
            
            badges = []
            badge_elems = container.find_all('div', class_='badge')
            for badge in badge_elems:
                badges.append(badge.text.strip())
            
            posts.append({
                "title": title,
                "link": link,
                "company": company,
                "role": role,
                "badges": badges
            })
            
        return posts
    except Exception as e:
        log(f"Error scraping page {page_url}: {e}")
        return []

def get_all_posts():
    """Get all posts from all pages"""
    all_posts = []
    current_page = 1
    
    while True:
        page_url = f"{BASE_URL}?page={current_page}" if current_page > 1 else BASE_URL
        log(f"Scraping page {current_page}: {page_url}")
        
        page_posts = get_page_posts(page_url)
        if not page_posts:
            log("No more pages found")
            break
            
        all_posts.extend(page_posts)
        current_page += 1
        
        # Check for next page button
        response = requests.get(page_url)
        soup = BeautifulSoup(response.text, 'html.parser')
        next_button = soup.find('li', class_='paginationjs-next')
        if not next_button:
            log("No next page button found")
            break
            
    return all_posts

def save_to_file(posts, filename):
    """Save posts to JSON file"""
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(posts, f, indent=2, ensure_ascii=False)
        log(f"Saved {len(posts)} posts to {filename}")
    except Exception as e:
        log(f"Error saving file: {e}")

if __name__ == "__main__":
    log("Starting full site scraper...")
    all_posts = get_all_posts()
    save_to_file(all_posts, OUTPUT_FILE)
    log("Scraping completed!")