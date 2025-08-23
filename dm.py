import requests
from bs4 import BeautifulSoup
import time
import json

# Configuration
TELEGRAM_TOKEN = "8496239540:AAG-S0RR1ReXY349kR3TdOjB5gCHAHNbNnU"
CHAT_ID = "6893240036"
URL = "https://deshimula.com/"
STATE_FILE = "seen_posts.json"

def get_latest_posts():
    """Scrape new posts from deshimula.com"""
    try:
        response = requests.get(URL)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        posts = []
        title_elements = soup.find_all('div', class_='post-title')
        for title_elem in title_elements:
            title = title_elem.text.strip()
            link_elem = title_elem.find_next('a', class_='hyper-link')
            link = link_elem['href'] if link_elem else None
            
            if title and link:
                posts.append({"title": title, "link": link})
                
        return posts
    except Exception as e:
        print(f"Error scraping: {e}")
        return []

def load_seen_posts():
    """Load previously seen posts from state file"""
    try:
        with open(STATE_FILE, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return []

def save_seen_posts(posts):
    """Save current posts to state file"""
    with open(STATE_FILE, 'w') as f:
        json.dump(posts, f)

def send_telegram_alert(title, link):
    """Send alert via Telegram"""
    message = f"*New Post:* [{title}]({link})"
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }
    try:
        requests.post(url, data=payload)
    except Exception as e:
        print(f"Telegram error: {e}")

if __name__ == "__main__":
    seen_posts = load_seen_posts()
    
    while True:
        current_posts = get_latest_posts()
        new_posts = [
            post for post in current_posts 
            if post not in seen_posts
        ]
        
        if new_posts:
            for post in new_posts:
                send_telegram_alert(post["title"], post["link"])
            seen_posts.extend(new_posts)
            save_seen_posts(seen_posts)
        
        time.sleep(300)  # Check every 5 minutes