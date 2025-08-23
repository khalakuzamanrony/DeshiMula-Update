import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import time
import json
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration from environment variables
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
URL = "https://deshimula.com/"
STATE_FILE = "seen_posts.json"


# Validate required environment variables
if not TELEGRAM_TOKEN or not CHAT_ID:
    print("ERROR: Missing environment variables!")
    print("Please create a .env file with:")
    print("TELEGRAM_TOKEN=your_token_here")
    print("CHAT_ID=your_chat_id_here")
    raise ValueError("TELEGRAM_TOKEN and CHAT_ID must be set in environment variables")

def get_main_page_posts():
    """Scrape basic info (title, link, author, badges) from the main page"""
    try:
        response = requests.get(URL)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        posts = []
        # Find all post containers (adjust selector if needed)
        post_containers = soup.find_all('div', class_='container mt-5')[:1]  # Only first post
        
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
            badges = {}
            negative_badge = container.find('div', class_='badge bg-danger soft')
            if negative_badge:
                badges["negative"] = negative_badge.text.strip()
            
            not_verified_badge = container.find('div', class_='badge bg-secondary soft')
            if not_verified_badge:
                badges["not_verified"] = not_verified_badge.text.strip()
            
            verified_badge = container.find('div', class_='badge bg-secondary soft')
            if verified_badge:
                badges["verified"] = verified_badge.text.strip()
            
            mixed_badge = container.find('div', class_='badge bg-secondary soft')
            if mixed_badge:
                badges["mixed"] = mixed_badge.text.strip()
            
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
                return []
            return json.loads(content)
    except (FileNotFoundError, json.JSONDecodeError):
        return []

def save_seen_posts(posts):
    """Save current posts to state file"""
    with open(STATE_FILE, 'w') as f:
        json.dump(posts, f)

def send_telegram_alert(title, link, company, role, badges):
    """Send alert via Telegram with full post details"""
    badge_text = ""
    if badges.get("negative"):
        badge_text += f"\n👎 Negative Badge: {badges['negative']}"
    if badges.get("not_verified"):
        badge_text += f"\n❌ Not Verified: {badges['not_verified']}"
    if badges.get("positive"):
        badge_text += f"\n✅ Positive: {badges['positive']}"
    if badges.get("mixed"):
        badge_text += f"\n⚖️ Mixed: {badges['mixed']}"

    message = (
        f"*New Review:*\n\n"
        f"Title: {title}\n"
        f"Author: {company} ({role})\n"
        f"{badge_text}\n"
        f"[Read Full]({link})\n"


    )
    
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }
    try:
        response = requests.post(url, data=payload)
        if response.status_code == 200:
            print(f"✅ Telegram notification sent: {title}")
        else:
            print(f"❌ Failed to send Telegram message: {response.status_code}")
    except Exception as e:
        print(f"❌ Telegram API error: {e}")

if __name__ == "__main__":
    print("🔍 DeshiMula Review Monitor Started")
    
    seen_posts = load_seen_posts()
    print(f"📋 Loaded {len(seen_posts)} previously seen posts")
    
    print("🌐 Checking for new posts...")
    current_posts = get_main_page_posts()
    print(f"📊 Found {len(current_posts)} current posts on the website")
    
    new_posts = [
        post for post in current_posts 
        if post not in seen_posts
    ]
    
    if new_posts:
        print(f"🆕 Found {len(new_posts)} new posts to process")
        for post in new_posts:
            print(f"📝 Processing: {post['title']}")
            # Fetch full content from the post's detail page
            content = get_post_content(post["link"])
            send_telegram_alert(
                title=post["title"],
                link=post["link"],
                company=post["company"],
                role=post["role"],
                badges=post["badges"],
            )
        
        seen_posts.extend(new_posts)
        save_seen_posts(seen_posts)
        print(f"💾 Updated seen posts file with {len(new_posts)} new entries")
        print(f"✅ Monitoring complete - {len(new_posts)} notifications sent")
    else:
        print("ℹ️  No new posts found - all posts already processed")
        print("✅ Monitoring complete - no action needed")