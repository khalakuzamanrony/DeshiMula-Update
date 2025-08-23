import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import time
import json
import os
from dotenv import load_dotenv
import cloudscraper

# Load environment variables
load_dotenv()

# Configuration from environment variables
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
BASE_URL = "https://deshimula.com/"
OUTPUT_FILE = "all_posts.json"

# Validate required environment variables
if not TELEGRAM_TOKEN or not CHAT_ID:
    print("ERROR: Missing environment variables!")
    print("Please create a .env file with:")
    print("TELEGRAM_TOKEN=your_token_here")
    print("CHAT_ID=your_chat_id_here")
    print(f"Current TELEGRAM_TOKEN: {'SET' if TELEGRAM_TOKEN else 'NOT SET'}")
    print(f"Current CHAT_ID: {'SET' if CHAT_ID else 'NOT SET'}")
    raise ValueError("TELEGRAM_TOKEN and CHAT_ID must be set in environment variables")

def log(msg):
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}")

def send_telegram_notification(message):
    """Send notification to Telegram"""
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {
            'chat_id': CHAT_ID,
            'text': message,
            'parse_mode': 'HTML',
            'disable_web_page_preview': False
        }
        response = requests.post(url, data=payload, timeout=30)
        if response.status_code == 200:
            log("Telegram notification sent successfully")
            return True
        else:
            log(f"Failed to send Telegram notification: {response.status_code}")
            log(f"Response text: {response.text}")
            return False
    except Exception as e:
        log(f"Error sending Telegram notification: {e}")
        return False

def format_post_message(post):
    """Format a post for Telegram message"""
    badges_text = ", ".join(post['badges']) if post['badges'] else "No badges"
    message = f"""🔔 <b>New Review Post Found!</b>

📋 <b>Title:</b> {post['title']}
🏢 <b>Company:</b> {post['company']}
👤 <b>Role:</b> {post['role']}
🏷️ <b>Type:</b> {badges_text}
🔗 <b>Link:</b> <a href="{post['link']}">View Full Post</a>"""
    return message

def get_page_posts(url):
    """Get posts from a single page with Cloudflare bypass"""
    try:
        log(f"🌐 Fetching URL: {url}")
        
        # Try cloudscraper first (best for Cloudflare bypass)
        try:
            log("🛡️ Attempting Cloudflare bypass with cloudscraper...")
            scraper = cloudscraper.create_scraper(
                browser={
                    'browser': 'chrome',
                    'platform': 'windows',
                    'desktop': True
                }
            )
            response = scraper.get(url, timeout=30)
            log(f"📡 Cloudscraper - Response status: {response.status_code}")
            
        except Exception as e:
            log(f"⚠️ Cloudscraper failed: {e}")
            log("🔄 Falling back to requests with headers...")
            
            # Fallback to requests with multiple attempts
            session = requests.Session()
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept-Encoding': 'gzip, deflate, br',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
                'Sec-Fetch-Dest': 'document',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Site': 'none',
                'Sec-Fetch-User': '?1',
            }
            
            response = session.get(url, headers=headers, timeout=30)
            log(f"📡 Requests fallback - Response status: {response.status_code}")
            
            # If still blocked, try with delay
            if response.status_code == 403 or "Just a moment" in response.text:
                log("🛡️ Still blocked - waiting and retrying...")
                time.sleep(8)
                headers['User-Agent'] = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
                response = session.get(url, headers=headers, timeout=30)
                log(f"📡 Final attempt - Response status: {response.status_code}")
        
        log(f"📄 Response length: {len(response.text)} characters")
        soup = BeautifulSoup(response.text, 'html.parser')
        
        posts = []
        post_containers = soup.find_all('div', class_='container mt-5')
        log(f"🔍 Found {len(post_containers)} post containers")
        
        # Debug: Print first 1000 chars of HTML to see structure
        if len(post_containers) == 0:
            log(f"📝 HTML sample: {response.text[:1000]}...")
            log("🔍 Trying alternative selectors...")
            alt_containers = soup.find_all('div', class_='container')
            log(f"🔍 Found {len(alt_containers)} containers with class 'container'")
        
        for container in post_containers:
            # Extract title
            title_elem = container.find('div', class_='post-title')
            title = title_elem.text.strip() if title_elem else None
            
            # Extract link
            link_elem = container.find('a', class_='hyper-link')
            link = urljoin(BASE_URL, link_elem['href']) if link_elem else None
            
            # Extract company
            company_elem = container.find('span', class_='company-name')
            company = company_elem.text.strip() if company_elem else None
            
            # Extract role
            role_elem = container.find('span', class_='reviewer-role')
            role = role_elem.text.strip() if role_elem else None
            
            # Extract badges
            badges = []
            badge_elems = container.find_all('div', class_='badge')
            for badge in badge_elems:
                badges.append(badge.text.strip())
            
            if title and link:
                posts.append({
                    "title": title,
                    "link": link,
                    "company": company,
                    "role": role,
                    "badges": badges
                })
        
        return posts
    except Exception as e:
        log(f"Error scraping page {url}: {e}")
        return []

def load_existing_posts(filename):
    """Load existing posts from file"""
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        log("No existing posts file found, starting fresh")
        return []
    except Exception as e:
        log(f"Error loading existing posts: {e}")
        return []

def get_all_posts():
    """Get all posts from all pages - only scrape new pages"""
    all_posts = []
    current_page = 1
    
    # Load existing posts to determine where to start scraping
    existing_posts = load_existing_posts(OUTPUT_FILE)
    existing_links = {post['link'] for post in existing_posts} if existing_posts else set()
    
    while True:
        if current_page == 1:
            page_url = BASE_URL
        else:
            page_url = f"{BASE_URL}stories/{current_page}"
        log(f"Scraping page {current_page}: {page_url}")
        
        page_posts = get_page_posts(page_url)
        if not page_posts:
            log("No more pages found")
            break
        
        # Check if all posts on this page already exist
        page_links = {post['link'] for post in page_posts}
        if existing_links and page_links.issubset(existing_links):
            log(f"Page {current_page} already fully scraped - stopping here")
            # Add existing posts from this page onwards to maintain order
            remaining_posts = [post for post in existing_posts if post['link'] in page_links]
            all_posts.extend(remaining_posts)
            break
            
        all_posts.extend(page_posts)
        current_page += 1
        
        # Check for next page button - simplified approach
        response = requests.get(page_url)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Look for pagination container and check if there are more pages
        pagination_container = soup.find('div', class_='pagination-container')
        if not pagination_container:
            pagination_container = soup.find('ul', class_='pagination')
        
        # Try to find next page link by looking for stories/{number} format
        page_links = soup.find_all('a', href=True)
        next_page_exists = False
        
        for link in page_links:
            href = link.get('href', '')
            if f'stories/{current_page + 1}' in href:
                next_page_exists = True
                break
        
        # Also check if we can construct next page URL and test if it has content
        if not next_page_exists:
            next_page_url = f"{BASE_URL}stories/{current_page + 1}"
            log(f"Testing next page URL: {next_page_url}")
            try:
                test_response = requests.get(next_page_url)
                test_soup = BeautifulSoup(test_response.text, 'html.parser')
                test_posts = test_soup.find_all('div', class_='container mt-5')
                log(f"Test page response status: {test_response.status_code}")
                log(f"Test page found {len(test_posts)} post containers")
                if test_posts and test_response.status_code == 200:
                    next_page_exists = True
                    log(f"✅ Page {current_page + 1} has content - continuing")
                else:
                    log(f"❌ Page {current_page + 1} has no posts or returned error - stopping")
            except Exception as e:
                log(f"Error testing page {current_page + 1}: {e}")
        
        if not next_page_exists:
            log(f"No more pages found after page {current_page}")
            break
            
    return all_posts

def find_new_posts(current_posts, existing_posts):
    """Find new posts by comparing with existing ones"""
    existing_links = {post['link'] for post in existing_posts}
    new_posts = [post for post in current_posts if post['link'] not in existing_links]
    return new_posts

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
    
    # Load existing posts
    existing_posts = load_existing_posts(OUTPUT_FILE)
    log(f"Loaded {len(existing_posts)} existing posts")
    
    # Get current posts
    current_posts = get_all_posts()
    log(f"Found {len(current_posts)} total posts")
    
    # Find new posts
    new_posts = find_new_posts(current_posts, existing_posts)
    log(f"Found {len(new_posts)} new posts")
    
    # Send notifications for new posts
    if new_posts:
        send_telegram_notification(f"🎉 Found {len(new_posts)} new job posts on DeshiMula!")
        
        # Reverse the order so latest posts (from page 1) are sent first
        for post in reversed(new_posts):
            message = format_post_message(post)
            send_telegram_notification(message)
            time.sleep(1)  # Rate limiting
    else:
        log("No new posts found")
    
    # Save all posts
    save_to_file(current_posts, OUTPUT_FILE)
    log("Scraping completed!")