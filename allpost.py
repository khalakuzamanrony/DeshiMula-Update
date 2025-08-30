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
STATE_FILE = "seen_posts.json"
MAX_POSTS = 150  # Maximum posts to keep in circular buffer

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
    """Send notification to Telegram with retry mechanism"""
    max_retries = 3
    for attempt in range(max_retries):
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
            elif response.status_code == 429:
                # Rate limited - extract retry_after from response
                try:
                    error_data = response.json()
                    retry_after = error_data.get('parameters', {}).get('retry_after', 30)
                    log(f"Rate limited. Waiting {retry_after} seconds before retry...")
                    time.sleep(retry_after + 1)
                except:
                    log("Rate limited. Waiting 30 seconds before retry...")
                    time.sleep(30)
                continue
            else:
                log(f"Failed to send Telegram notification: {response.status_code}")
                log(f"Response text: {response.text}")
                if attempt < max_retries - 1:
                    log(f"Retrying in 5 seconds...")
                    time.sleep(5)
                    continue
                return False
        except Exception as e:
            log(f"Error sending Telegram notification: {e}")
            if attempt < max_retries - 1:
                log(f"Retrying in 5 seconds...")
                time.sleep(5)
                continue
            return False
    
    return False

def format_post_message(post, count=None):
    """Format a post for Telegram message"""
    badges_text = ", ".join(post['badges']) if post['badges'] else "No badges"
    count_text = f" #{count}" if count else ""
    
    message = f"""🚨 <b>New Review Alert!{count_text}</b>

📝 <b>Title:</b> {post['title']}
🏢 <b>Company:</b> {post['company']}
💼 <b>Role:</b> {post['role']}
🏷️ <b>Type:</b> {badges_text}

🔗 <a href="{post['link']}">View Full Post</a>"""
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
                # Create unique identifier for each post
                post_id = f"{title}_{link}"
                posts.append({
                    "id": post_id,
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

def load_seen_posts():
    """Load previously seen posts from state file"""
    try:
        with open(STATE_FILE, 'r', encoding='utf-8') as f:
            content = f.read().strip()
            if not content:
                return []
            posts = json.loads(content)
            if not isinstance(posts, list):
                return []
            return posts
    except FileNotFoundError:
        log("No existing posts file found, starting fresh")
        return []
    except json.JSONDecodeError as e:
        log(f"JSON decode error: {e}")
        log("Backing up corrupted file and starting fresh...")
        import shutil
        shutil.move(STATE_FILE, f"{STATE_FILE}.backup")
        return []
    except Exception as e:
        log(f"Error loading seen posts: {e}")
        return []

def save_seen_posts_with_buffer(posts):
    """Save posts with circular buffer management (max 150 posts)"""
    # Limit to MAX_POSTS
    if len(posts) > MAX_POSTS:
        posts = posts[:MAX_POSTS]
        log(f"Buffer limit reached. Keeping newest {MAX_POSTS} posts, removed {len(posts) - MAX_POSTS} old posts")
    
    # Add index to all posts
    for i, post in enumerate(posts):
        post['index'] = i
    
    with open(STATE_FILE, 'w', encoding='utf-8') as f:
        json.dump(posts, f, indent=2, ensure_ascii=False)
    
    log(f"Saved {len(posts)} posts to buffer (max: {MAX_POSTS})")

def find_new_posts(current_posts, seen_posts):
    """Find new posts by comparing with existing posts"""
    seen_post_ids = set()
    for post in seen_posts:
        post_id = post.get('id', f"{post.get('title', '')}_{post.get('link', '')}")
        seen_post_ids.add(post_id)
    
    new_posts = []
    for post in current_posts:
        post_id = post.get('id', f"{post.get('title', '')}_{post.get('link', '')}")
        if post_id not in seen_post_ids:
            new_posts.append(post)
    
    return new_posts

def update_buffer_with_new_posts(new_posts, existing_posts):
    """Update circular buffer: preserve website ordering, limit to 150 posts"""
    # Simply use the current scraped posts as they maintain website order
    # New posts are already in correct order from scraping
    current_posts = new_posts  # These are in website order (0-149)
    
    # Apply circular buffer limit - keep first 150 posts (website order)
    if len(current_posts) > MAX_POSTS:
        current_posts = current_posts[:MAX_POSTS]
    
    return current_posts

def get_all_posts():
    """Get all posts from all pages starting from page 2"""
    all_posts = []
    current_page = 2  # Start from page 2, skip first page
    
    while True:
        page_url = f"{BASE_URL}stories/{current_page}"
        log(f"Scraping page {current_page}: {page_url}")
        
        page_posts = get_page_posts(page_url)
        if not page_posts:
            log(f"No more pages found after page {current_page-1}")
            break
            
        all_posts.extend(page_posts)
        current_page += 1
        
        # Test next page with cloudscraper to avoid Cloudflare blocks
        next_page_url = f"{BASE_URL}stories/{current_page + 1}"
        log(f"Testing next page URL: {next_page_url}")
        try:
            # Use cloudscraper for testing next page
            scraper = cloudscraper.create_scraper(
                browser={
                    'browser': 'chrome',
                    'platform': 'windows',
                    'desktop': True
                }
            )
            test_response = scraper.get(next_page_url, timeout=30)
            test_soup = BeautifulSoup(test_response.text, 'html.parser')
            test_posts = test_soup.find_all('div', class_='container mt-5')
            log(f"Test page response status: {test_response.status_code}")
            log(f"Test page found {len(test_posts)} post containers")
            
            if len(test_posts) > 0:
                log(f"✅ Page {current_page + 1} has content - continuing")
            else:
                log(f"❌ Page {current_page + 1} has no posts or returned error - stopping")
                break
        except Exception as e:
            log(f"Error testing next page: {e}")
            break
    
    return all_posts

# Circular buffer functions integrated above

if __name__ == "__main__":
    log("🔍 DeshiMula All Posts Monitor Started (Starting from Page 2)")
    
    # Load existing posts from circular buffer
    existing_posts = load_seen_posts()
    log(f"📊 Buffer Status: {len(existing_posts)}/{MAX_POSTS} posts")
    log(f"📋 Loaded {len(existing_posts)} existing posts from buffer")
    
    # Get current posts from all pages (starting from page 2)
    log("🌐 Scraping all pages (skipping first page)...")
    current_posts = get_all_posts()
    log(f"📊 Found {len(current_posts)} total posts across all pages (excluding first page)")
    
    # Find new posts
    new_posts = find_new_posts(current_posts, existing_posts)
    log(f"🆕 Found {len(new_posts)} new posts")
    
    # Send notifications for new posts in reverse order (so last post gets #1)
    if new_posts:
        log(f"Sending {len(new_posts)} notifications to Telegram...")
        
        # Send posts in reverse order so last post gets #1, second last gets #2, etc.
        for i, post in enumerate(reversed(new_posts), 1):
            log(f"📝 Processing #{i}: {post['title']}")
            message = format_post_message(post, i)
            if send_telegram_notification(message):
                log(f"✅ Sent notification #{i}")
            else:
                log(f"❌ Failed to send notification #{i}")
            time.sleep(3)  # Increased rate limiting to 3 seconds
        
        log(f"📊 Completed sending {len(new_posts)} notifications")
        
        # Update circular buffer with current posts (preserves website ordering)
        updated_buffer = update_buffer_with_new_posts(current_posts, existing_posts)
        save_seen_posts_with_buffer(updated_buffer)
    else:
        log("No new posts found")
        # Still update the buffer with current posts to maintain website ordering
        updated_buffer = update_buffer_with_new_posts(current_posts, existing_posts)
        save_seen_posts_with_buffer(updated_buffer)
    
    # Show final buffer statistics
    final_posts = load_seen_posts()
    available_slots = MAX_POSTS - len(final_posts)
    log(f"📈 Final Buffer: {len(final_posts)}/{MAX_POSTS} posts, {available_slots} slots available")
    log("✅ All posts scraping completed!")