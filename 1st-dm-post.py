import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import time
import json
import os
from dotenv import load_dotenv
import cloudscraper
from datetime import datetime

# Load environment variables
load_dotenv()

# Configuration from environment variables
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
URL = "https://deshimula.com/"
STATE_FILE = "seen_posts.json"
MAX_POSTS = 30  # Number of posts to scrape from first page


# Validate required environment variables
if not TELEGRAM_TOKEN or not CHAT_ID:
    print("ERROR: Missing environment variables!")
    print("Please create a .env file with:")
    print("TELEGRAM_TOKEN=your_token_here")
    print("CHAT_ID=your_chat_id_here")
    print(f"Current TELEGRAM_TOKEN: {'SET' if TELEGRAM_TOKEN else 'NOT SET'}")
    print(f"Current CHAT_ID: {'SET' if CHAT_ID else 'NOT SET'}")
    raise ValueError("TELEGRAM_TOKEN and CHAT_ID must be set in environment variables")

def get_main_page_posts():
    """Scrape basic info (title, link, author, badges) from the main page"""
    try:
        print(f"🌐 Fetching URL: {URL}")
        
        # Try cloudscraper first (best for Cloudflare bypass)
        try:
            print("🛡️ Attempting Cloudflare bypass with cloudscraper...")
            scraper = cloudscraper.create_scraper(
                browser={
                    'browser': 'chrome',
                    'platform': 'windows',
                    'desktop': True
                }
            )
            response = scraper.get(URL, timeout=30)
            print(f"📡 Cloudscraper - Response status: {response.status_code}")
            
        except Exception as e:
            print(f"⚠️ Cloudscraper failed: {e}")
            print("🔄 Falling back to requests with headers...")
            
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
            
            response = session.get(URL, headers=headers, timeout=30)
            print(f"📡 Requests fallback - Response status: {response.status_code}")
            
            # If still blocked, try with delay
            if response.status_code == 403 or "Just a moment" in response.text:
                print("🛡️ Still blocked - waiting and retrying...")
                time.sleep(8)
                headers['User-Agent'] = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
                response = session.get(URL, headers=headers, timeout=30)
                print(f"📡 Final attempt - Response status: {response.status_code}")
        print(f"📡 Response status: {response.status_code}")
        print(f"📄 Response length: {len(response.text)} characters")
        soup = BeautifulSoup(response.text, 'html.parser')
        
        posts = []
        # Find all post containers (adjust selector if needed)
        post_containers = soup.find_all('div', class_='container mt-5')[:MAX_POSTS]  # First 30 posts
        print(f"🔍 Found {len(post_containers)} post containers")
        
        # Debug: Print first 1000 chars of HTML to see structure
        print(f"📝 HTML sample: {response.text[:1000]}...")
        
        # Also try alternative selectors in case the structure is different
        if len(post_containers) == 0:
            print("🔍 Trying alternative selectors...")
            alt_containers = soup.find_all('div', class_='container')
            print(f"🔍 Found {len(alt_containers)} containers with class 'container'")
            
            # Look for any divs that might contain posts
            all_divs = soup.find_all('div')
            post_like_divs = [div for div in all_divs if 'post' in str(div.get('class', [])).lower()]
            print(f"🔍 Found {len(post_like_divs)} divs with 'post' in class name")
            
            # Check for specific elements that indicate posts
            titles = soup.find_all('div', class_='post-title')
            links = soup.find_all('a', class_='hyper-link')
            print(f"🔍 Found {len(titles)} post-title elements")
            print(f"🔍 Found {len(links)} hyper-link elements")
        
        for container in post_containers:
            # Extract title
            title_elem = container.find('div', class_='post-title')
            title = title_elem.text.strip() if title_elem else None
            
            # Extract link (now properly joined to base URL)
            link_elem = container.find('a', class_='hyper-link')
            link = urljoin(URL, link_elem['href']) if link_elem else None
            
            # Extract author/company
            company_elem = container.find('span', class_='company-name')
            company = company_elem.text.strip() if company_elem else None
            
            # Extract reviewer role
            role_elem = container.find('span', class_='reviewer-role')
            role = role_elem.text.strip() if role_elem else None


            # Extract type
            role_elem = container.find('span', class_='reviewer-role')
            role = role_elem.text.strip() if role_elem else None
            
            # Extract badges (if any)
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
        print(f"Error scraping main page: {e}")
        return []

def get_post_content(post_link):
    """Fetch full content from the post's detail page"""
    try:
        response = requests.get(post_link)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Locate the content section (adjust selector based on actual structure)
        content_div = soup.find('div', class_='company-review')
        content = content_div.text.strip() if content_div else "Content not found"
        
        return content
    except Exception as e:
        print(f"Error fetching post content: {e}")
        return "Failed to load content"

def load_seen_posts():
    """Load previously seen posts from state file"""
    try:
        with open(STATE_FILE, 'r') as f:
            content = f.read().strip()
            if not content:
                return None  # Empty file
            return json.loads(content)
    except (FileNotFoundError, json.JSONDecodeError):
        return None  # File doesn't exist or is corrupted

def save_seen_posts(posts):
    """Save current posts to state file"""
    with open(STATE_FILE, 'w') as f:
        json.dump(posts, f)

def send_telegram_alert(title, link, company, role, badges, count=None):
    """Send alert via Telegram with full post details"""
    badge_text = ", ".join(badges) if badges else "No badges"
    count_text = f" #{count}" if count else ""
    
    message = f"""
🚨 *New Review Alert!{count_text}*

📝 *Title:* {title}
🏢 *Company:* {company}
💼 *Role:* {role}
🏷️ *Type:* {badge_text}

🔗 [View Full Post]({link})
"""
    
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        'chat_id': CHAT_ID,
        'text': message,
        'parse_mode': 'Markdown',
        'disable_web_page_preview': False
    }
    
    try:
        print(f"🔄 Sending Telegram notification for: {title}")
        response = requests.post(url, data=payload)
        print(f"📡 Telegram API Response: {response.status_code}")
        if response.status_code == 200:
            print(f"✅ Telegram notification sent: {title}")
        else:
            print(f"❌ Failed to send Telegram message: {response.status_code}")
            print(f"Response: {response.text}")
    except Exception as e:
        print(f"❌ Telegram API error: {e}")

if __name__ == "__main__":
    print(f"🔍 DeshiMula Review Monitor Started - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    seen_posts = load_seen_posts()
    
    print("🌐 Checking for new posts...")
    current_posts = get_main_page_posts()
    print(f"📊 Found {len(current_posts)} current posts on the website")
    
    # If seen_posts.json doesn't exist or is empty, initialize with current posts
    if seen_posts is None:
        print("📄 No previous posts file found - initializing with current posts")
        print(f"🆕 Found {len(current_posts)} posts to process (first run)")
        
        # Send notifications for all current posts on first run (reverse order)
        for i, post in enumerate(reversed(current_posts), 1):
            print(f"📝 Processing #{len(current_posts) - i + 1}: {post['title']}")
            send_telegram_alert(
                title=post["title"],
                link=post["link"],
                company=post["company"],
                role=post["role"],
                badges=post["badges"],
                count=len(current_posts) - i + 1
            )
        
        save_seen_posts(current_posts)
        print(f"💾 Created seen_posts.json with {len(current_posts)} posts")
        print(f"✅ Initialization complete - {len(current_posts)} notifications sent")
    else:
        print(f"📋 Loaded {len(seen_posts)} previously seen posts")
        
        # Create sets of post IDs for efficient comparison
        seen_post_ids = {post.get('id', f"{post['title']}_{post['link']}") for post in seen_posts}
        
        # Find new posts by comparing IDs
        new_posts = [
            post for post in current_posts 
            if post['id'] not in seen_post_ids
        ]
        
        if new_posts:
            print(f"🆕 Found {len(new_posts)} new posts to process")
            for i, post in enumerate(reversed(new_posts), 1):
                print(f"📝 Processing #{len(new_posts) - i + 1}: {post['title']}")
                send_telegram_alert(
                    title=post["title"],
                    link=post["link"],
                    company=post["company"],
                    role=post["role"],
                    badges=post["badges"],
                    count=len(new_posts) - i + 1
                )
            
            # Update seen_posts with current_posts (replace old data with new scrape)
            save_seen_posts(current_posts)
            print(f"💾 Updated seen posts file - stored {len(current_posts)} total posts")
            print(f"✅ Monitoring complete - {len(new_posts)} notifications sent")
        else:
            print("ℹ️  No new posts found - all posts already processed")
            # Still update the stored data with current scrape
            save_seen_posts(current_posts)
            print(f"💾 Updated seen posts file - stored {len(current_posts)} total posts")
            print("✅ Monitoring complete - no action needed")