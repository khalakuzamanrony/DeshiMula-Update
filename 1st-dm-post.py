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
BASE_URL = "https://deshimula.com/"
STATE_FILE = "seen_posts.json"
MAX_PAGES = 5  # Number of pages to scrape (first 5 pages)


# Validate required environment variables
if not TELEGRAM_TOKEN or not CHAT_ID:
    print("ERROR: Missing environment variables!")
    print("Please create a .env file with:")
    print("TELEGRAM_TOKEN=your_token_here")
    print("CHAT_ID=your_chat_id_here")
    print(f"Current TELEGRAM_TOKEN: {'SET' if TELEGRAM_TOKEN else 'NOT SET'}")
    print(f"Current CHAT_ID: {'SET' if CHAT_ID else 'NOT SET'}")
    raise ValueError("TELEGRAM_TOKEN and CHAT_ID must be set in environment variables")

def get_page_posts(page_url):
    """Scrape posts from a single page"""
    try:
        print(f"🌐 Fetching URL: {page_url}")
        
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
            response = scraper.get(page_url, timeout=30)
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
            
            response = session.get(page_url, headers=headers, timeout=30)
            print(f"📡 Requests fallback - Response status: {response.status_code}")
            
            # If still blocked, try with delay
            if response.status_code == 403 or "Just a moment" in response.text:
                print("🛡️ Still blocked - waiting and retrying...")
                time.sleep(8)
                headers['User-Agent'] = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
                response = session.get(page_url, headers=headers, timeout=30)
                print(f"📡 Final attempt - Response status: {response.status_code}")
        
        print(f"📡 Response status: {response.status_code}")
        print(f"📄 Response length: {len(response.text)} characters")
        soup = BeautifulSoup(response.text, 'html.parser')
        
        posts = []
        # Find all post containers
        post_containers = soup.find_all('div', class_='container mt-5')
        print(f"🔍 Found {len(post_containers)} post containers on this page")
        
        for container in post_containers:
            # Extract title
            title_elem = container.find('div', class_='post-title')
            title = title_elem.text.strip() if title_elem else None
            
            # Extract link (properly joined to base URL)
            link_elem = container.find('a', class_='hyper-link')
            link = urljoin(BASE_URL, link_elem['href']) if link_elem else None
            
            # Extract author/company
            company_elem = container.find('span', class_='company-name')
            company = company_elem.text.strip() if company_elem else None
            
            # Extract reviewer role
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
        print(f"Error scraping page {page_url}: {e}")
        return []

def get_all_posts_from_pages():
    """Scrape posts from the first 5 pages"""
    all_posts = []
    
    for page_num in range(1, MAX_PAGES + 1):
        if page_num == 1:
            page_url = BASE_URL
        else:
            page_url = f"{BASE_URL}stories/{page_num}"
        
        print(f"📚 Scraping page {page_num}/{MAX_PAGES}: {page_url}")
        page_posts = get_page_posts(page_url)
        
        if page_posts:
            all_posts.extend(page_posts)
            print(f"✅ Page {page_num}: Found {len(page_posts)} posts")
        else:
            print(f"⚠️ Page {page_num}: No posts found")
        
        # Add delay between pages to avoid rate limiting
        if page_num < MAX_PAGES:
            time.sleep(2)
    
    print(f"📊 Total posts collected from {MAX_PAGES} pages: {len(all_posts)}")
    return all_posts

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
        with open(STATE_FILE, 'r', encoding='utf-8') as f:
            content = f.read().strip()
            if not content:
                return None  # Empty file
            return json.loads(content)
    except FileNotFoundError:
        return None  # File doesn't exist
    except json.JSONDecodeError as e:
        print(f"⚠️ JSON decode error: {e}")
        print("🔄 Backing up corrupted file and starting fresh...")
        # Backup corrupted file
        import shutil
        shutil.move(STATE_FILE, f"{STATE_FILE}.backup")
        return None
    except Exception as e:
        print(f"⚠️ Error loading seen posts: {e}")
        return None

def save_seen_posts(posts):
    """Save current posts to state file with proper formatting"""
    with open(STATE_FILE, 'w', encoding='utf-8') as f:
        json.dump(posts, f, indent=2, ensure_ascii=False)

def send_telegram_alert(title, link, company, role, badges, count=None):
    """Send alert via Telegram with full post details and retry mechanism"""
    badge_text = ", ".join(badges) if badges else "No badges"
    count_text = f" #{count}" if count else ""
    
    message = f"""
🚨 *New Review Alert!* 

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
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            print(f"🔄 Sending Telegram notification for: {title} (attempt {attempt + 1})")
            response = requests.post(url, data=payload, timeout=30)
            print(f"📡 Telegram API Response: {response.status_code}")
            
            if response.status_code == 200:
                print(f"✅ Telegram notification sent: {title}")
                return True
            elif response.status_code == 429:
                # Rate limited - extract retry_after from response
                try:
                    error_data = response.json()
                    retry_after = error_data.get('parameters', {}).get('retry_after', 30)
                    print(f"⏳ Rate limited. Waiting {retry_after} seconds before retry...")
                    time.sleep(retry_after + 1)  # Add 1 extra second
                except:
                    print("⏳ Rate limited. Waiting 30 seconds before retry...")
                    time.sleep(30)
                continue
            else:
                print(f"❌ Failed to send Telegram message: {response.status_code}")
                print(f"Response: {response.text}")
                if attempt < max_retries - 1:
                    print(f"🔄 Retrying in 5 seconds...")
                    time.sleep(5)
                    continue
                return False
        except Exception as e:
            print(f"❌ Telegram API error: {e}")
            if attempt < max_retries - 1:
                print(f"🔄 Retrying in 5 seconds...")
                time.sleep(5)
                continue
            return False
    
    return False

if __name__ == "__main__":
    print(f"🔍 DeshiMula Review Monitor Started - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    seen_posts = load_seen_posts()
    
    print(f"🌐 Checking for new posts from first {MAX_PAGES} pages...")
    current_posts = get_all_posts_from_pages()
    print(f"📊 Found {len(current_posts)} current posts from {MAX_PAGES} pages")
    
    # Handle both first run and subsequent runs
    if seen_posts is None:
        print("📄 No previous posts file found - first run detected")
        print(f"🆕 Found {len(current_posts)} posts from {MAX_PAGES} pages - sending all as notifications")
        
        # Send notifications for all current posts on first run (reverse order)
        for i, post in enumerate(reversed(current_posts), 1):
            print(f"📝 Processing #{i}: {post['title']}")
            send_telegram_alert(
                title=post["title"],
                link=post["link"],
                company=post["company"],
                role=post["role"],
                badges=post["badges"],
                count=i
            )
            time.sleep(3)  # Wait 3 seconds between messages to avoid rate limiting
        
        # Save current posts after sending notifications
        save_seen_posts(current_posts)
        print(f"💾 Created seen_posts.json with {len(current_posts)} posts")
        print(f"✅ First run complete - {len(current_posts)} notifications sent")
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
                print(f"📝 Processing #{i}: {post['title']}")
                send_telegram_alert(
                    title=post["title"],
                    link=post["link"],
                    company=post["company"],
                    role=post["role"],
                    badges=post["badges"],
                    count=i
                )
                time.sleep(3)  # Wait 3 seconds between messages to avoid rate limiting
            
            # Update seen_posts with current_posts (replace old data with new scrape)
            save_seen_posts(current_posts)
            print(f"💾 Updated seen posts file - stored {len(current_posts)} total posts")
            print(f"✅ Monitoring complete - {len(new_posts)} notifications sent")
        else:
            print("ℹ️  No new posts found - all posts already processed")
            # Still update the stored data with current scrape
            save_seen_posts(current_posts)
            print(f"💾 Updated seen posts file - stored {len(current_posts)} total posts")
            print("✅ Monitoring complete - no new notifications needed")