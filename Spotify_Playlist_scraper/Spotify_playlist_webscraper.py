import csv
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service
from bs4 import BeautifulSoup

# Spotify Top 100 Deutschland playlist
URL = "https://open.spotify.com/playlist/6doxjqiIce6uzxsHgBzRKE"


def fetch_page_with_selenium(url: str) -> BeautifulSoup:
    """Download page HTML using Selenium to handle JavaScript rendering."""
    print("Loading page with Selenium...")
    
    # Setup Chrome options to avoid Spotify blocking
    chrome_options = Options()
    chrome_options.add_argument("--start-maximized")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    
    # Initialize driver
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    
    try:
        driver.get(url)
        print(f"Page title: {driver.title}")
        
        # Wait for song rows to load
        wait = WebDriverWait(driver, 30)
        wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, "div[role='row']")))
        
        # Scroll to top first
        print("Scrolling to top of playlist...")
        driver.execute_script("""
            const mainScroller = document.querySelector('[role="main"]');
            if (mainScroller) {
                mainScroller.scrollTop = 0;
            }
        """)
        time.sleep(2)
        
        # Collect songs as we scroll - keep track of all positions seen
        print("Collecting first 100 songs by scrolling...")
        collected_soups = []
        collected_positions = set()
        
        for i in range(50):  # Multiple scroll iterations
            # Get current page source
            current_html = driver.page_source
            current_soup = BeautifulSoup(current_html, "html.parser")
            collected_soups.append(current_soup)
            
            # Extract positions to see what we have
            rows_check = current_soup.find_all("div", {"role": "row"})
            
            for row in rows_check:
                text = row.get_text()
                # Find position number
                for word in text.split():
                    if word.isdigit():
                        pos = int(word)
                        if 1 <= pos <= 500:
                            collected_positions.add(pos)
                            break
            
            # Show progress
            if i % 5 == 0:
                print(f"  Scroll {i+1}: Found {len(collected_positions)} unique songs (up to position {max(collected_positions) if collected_positions else 0})")
            
            # Stop if we have 100 songs
            if len(collected_positions) >= 100:
                print(f"✓ Collected 100+ songs!")
                break
            
            # Scroll down
            driver.execute_script("""
                const mainScroller = document.querySelector('[role="main"]');
                if (mainScroller) {
                    mainScroller.scrollTop += 300;
                }
            """)
            time.sleep(0.4)
        
        # Merge all soups into one by combining all their rows
        combined_html = "<html><body>"
        all_rows = []
        for soup in collected_soups:
            rows = soup.find_all("div", {"role": "row"})
            all_rows.extend(rows)
        
        # Remove duplicates based on text content
        seen_content = set()
        unique_rows = []
        for row in all_rows:
            content = row.get_text(strip=True)
            if content and content not in seen_content:
                seen_content.add(content)
                unique_rows.append(str(row))
        
        combined_html += "".join(unique_rows) + "</body></html>"
        soup = BeautifulSoup(combined_html, "html.parser")
        
        # Save original page for debugging
        with open("debug_page_source.html", "w", encoding="utf-8") as f:
            f.write(driver.page_source)
        driver.save_screenshot("debug_screenshot.png")
        
        print(f"Total unique songs collected: {len(collected_positions)}")
        return soup
    finally:
        driver.quit()


def extract_songs(soup: BeautifulSoup):
    """
    Extract song position, title, and artist from the Top 100 Deutschland playlist.
    """
    songs = []
    seen = set()
    
    # Find all song rows - Apple Music uses role="row" for each song
    song_rows = soup.find_all("div", {"role": "row"})
    
    print(f"Found {len(song_rows)} potential song rows")
    
    for idx, row in enumerate(song_rows):
        try:
            # Get all text content from the row
            row_text = row.get_text(strip=True)
            
            # Skip empty rows
            if not row_text:
                continue
            
            # Find position number - usually the first number in the row
            position = None
            for child in row.find_all(string=True):
                text = child.strip()
                if text.isdigit():
                    pos_int = int(text)
                    if 1 <= pos_int <= 200:
                        position = pos_int
                        break
            
            if position is None:
                continue
            
            # Find song title and artist - usually in links or specific span elements
            # Apple Music structure: song title and artist are typically in separate elements
            links = row.find_all("a")
            song_title = None
            artist = None
            
            # Extract song title from the first link
            if links:
                song_title = links[0].get_text(strip=True)
            
            # Extract artist - usually second link or following elements
            if len(links) > 1:
                artist = links[1].get_text(strip=True)
            
            # Fallback: extract from all text nodes
            if not (song_title and artist):
                text_nodes = [t.strip() for t in row.stripped_strings if t.strip() and len(t.strip()) > 1]
                
                if text_nodes:
                    # Filter out position numbers
                    text_nodes = [t for t in text_nodes if not t.isdigit()]
                    
                    if len(text_nodes) >= 2:
                        if not song_title:
                            song_title = text_nodes[0]
                        if not artist:
                            artist = text_nodes[1]
                    elif len(text_nodes) == 1:
                        if not song_title:
                            song_title = text_nodes[0]
            
            if not song_title:
                continue
            
            if not artist:
                artist = ""
            
            # Create unique key
            key = (position, song_title)
            
            if key not in seen:
                seen.add(key)
                songs.append({
                    "position": position,
                    "song_title": song_title,
                    "artist": artist,
                })
        except Exception as e:
            print(f"Error processing row {idx}: {e}")
            continue
    
    # Sort by position
    songs.sort(key=lambda x: x["position"])
    
    # Return only the first 100 songs
    return songs[:100]


def save_to_csv(songs, filename="Spotify_songs_webscrapped.csv"):
    """Save song data to a CSV file."""
    fieldnames = ["position", "song_title", "artist"]
    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for song in songs:
            writer.writerow(song)


def main():
    print("Downloading page…")
    soup = fetch_page_with_selenium(URL)
    print("Extracting songs…")
    songs = extract_songs(soup)
    print(f"Found {len(songs)} songs.")
    for song in songs:
        print(f"{song['position']:>3} | {song['song_title']} | {song['artist']}")
    save_to_csv(songs)
    print('Saved to "Spotify_songs_webscrapped.csv"')


if __name__ == "__main__":
    main()
