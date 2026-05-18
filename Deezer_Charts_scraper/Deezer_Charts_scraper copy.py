import csv
import re
import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service
import time

# Deezer charts URL
URL = "https://www.deezer.com/de/channels/module/3d720c8b-6256-4731-8f2f-28fafc60d0e1"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
}


def fetch_page_selenium(url: str):
    """Use Selenium to fetch the page with JavaScript rendering."""
    print("Starting Selenium WebDriver...")
    options = webdriver.ChromeOptions()
    options.add_argument("--start-maximized")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument(f"user-agent={HEADERS['User-Agent']}")
    
    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=options
    )
    
    try:
        print("Loading Deezer page...")
        driver.get(url)
        
        # Wait for page to load
        print("Waiting for page to fully render...")
        time.sleep(5)
        
        # Scroll to load all playlists
        print("Scrolling to load all playlists...")
        last_height = driver.execute_script("return document.body.scrollHeight")
        scroll_count = 0
        while scroll_count < 15:
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(1)
            new_height = driver.execute_script("return document.body.scrollHeight")
            if new_height == last_height:
                break
            last_height = new_height
            scroll_count += 1
        
        print(f"Completed scrolling after {scroll_count} scroll(s)")
        
        # Get the full page HTML
        page_source = driver.page_source
        return page_source
        
    finally:
        driver.quit()


def extract_playlists_from_html(html_content):
    """
    Extract playlist information from Deezer HTML using BeautifulSoup.
    The playlists are displayed in a grid that reads left-to-right, top-to-bottom.
    """
    playlists = []
    soup = BeautifulSoup(html_content, "html.parser")
    
    # Find all playlist list items (thumbnail-col)
    playlist_items = soup.find_all("li", attrs={"data-testid": "thumbnail-playlist-li"})
    
    print(f"Found {len(playlist_items)} playlist items")
    
    for idx, item in enumerate(playlist_items):
        try:
            # Find the playlist title link within the item
            title_link = item.find("a", attrs={"data-testid": "thumbnail-title"})
            if not title_link:
                continue
            
            # Get the playlist name and URL
            playlist_name = title_link.get_text(strip=True)
            playlist_url = title_link.get("href")
            
            if not playlist_name or not playlist_url:
                continue
            
            # Extract playlist ID from URL
            match = re.search(r'/playlist/(\d+)', playlist_url)
            if not match:
                continue
            
            playlist_id = match.group(1)
            
            # Find the fan count (in heading-5-sub class)
            fan_div = item.find("div", class_="heading-5-sub")
            fan_count = None
            
            if fan_div:
                fan_text = fan_div.get_text(strip=True)
                # Extract fan count from text like "92 Titel - 745.915 Fans"
                fan_match = re.search(r'(\d+(?:\.\d+)*)\s+Fans?', fan_text, re.IGNORECASE)
                if fan_match:
                    fan_count = fan_match.group(1).replace('.', '')  # Remove dots (German number formatting)
            
            if not fan_count:
                continue
            
            # Store the playlist
            playlists.append({
                "playlist_id": playlist_id,
                "playlist_name": playlist_name,
                "fans": fan_count,
                "url": f"https://www.deezer.com{playlist_url}",
            })
            
            if idx < 5:
                print(f"[DEBUG {idx}] {playlist_id}: {playlist_name} - {fan_count} fans")
        
        except Exception as e:
            print(f"Error extracting playlist {idx}: {e}")
            continue
    
    print(f"\nExtracted {len(playlists)} unique playlists")
    
    return playlists


def number_playlists_in_reading_order(playlists):
    """
    Add position numbers to playlists in reading order (left to right, top to bottom).
    Since the page is a grid, we'll number them based on their order in the DOM.
    """
    for i, playlist in enumerate(playlists, 1):
        playlist["position"] = i
    
    return playlists


def save_to_csv(playlists, filename="Deezer_Charts.csv"):
    """Save playlist data to a CSV file."""
    fieldnames = ["position", "playlist_name", "fans"]
    
    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for pl in playlists:
            writer.writerow({
                "position": pl["position"],
                "playlist_name": pl["playlist_name"],
                "fans": pl["fans"],
            })


def main():
    try:
        print("=" * 60)
        print("DEEZER CHARTS SCRAPER")
        print("=" * 60)
        
        html_content = fetch_page_selenium(URL)
        print("✓ Page loaded successfully")
        
        # Debug: save HTML to file
        with open("deezer_debug.html", "w", encoding="utf-8") as f:
            f.write(html_content)
        print("✓ Saved HTML to deezer_debug.html")
        
        playlists = extract_playlists_from_html(html_content)
        
        playlists = number_playlists_in_reading_order(playlists)
        
        # Display results
        print("\nPlaylists (reading order: left to right, top to bottom):")
        print("-" * 80)
        for pl in playlists[:20]:  # Show first 20
            print(f"{pl['position']:3d} | {pl['playlist_name']:<40} | {pl['fans']:>8} Fans")
        
        if len(playlists) > 20:
            print(f"... and {len(playlists) - 20} more playlists")
        
        save_to_csv(playlists)
        print(f"\n✓ Saved {len(playlists)} playlists to 'Deezer_Charts.csv'")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
