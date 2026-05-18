import csv
import time
import random
from bs4 import BeautifulSoup
from selenium import webdriver

# 1. Put the URL of the Apple Music "Top-Playlists" page here
URL = "https://music.apple.com/de/new/top-charts/playlists"  # e.g. the page you're looking at in your browser

# 2. Basic headers so Apple Music doesn't immediately block the request
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
}


def fetch_page_with_selenium(url: str, min_playlists: int = 200) -> BeautifulSoup:
    """Download page HTML using Selenium and scroll to load more content."""
    print(f"Loading page with Selenium (target: {min_playlists} playlists)...")
    driver = webdriver.Chrome()
    try:
        driver.get(url)
        time.sleep(5)  # Wait for initial load

        # Scroll down aggressively to load more playlists
        last_height = driver.execute_script("return document.body.scrollHeight")
        playlists_loaded = 0
        scroll_attempts = 0
        max_scrolls = 30

        while scroll_attempts < max_scrolls:
            # Scroll down
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(random.uniform(2.0, 3.5))  # Wait longer for content to load

            # Check how many playlists we have
            soup = BeautifulSoup(driver.page_source, "html.parser")
            chart_section = None
            for section in soup.find_all(["section", "main", "div"]):
                if section.get_text(strip=True).startswith("Top-Playlists"):
                    chart_section = section
                    break

            if chart_section:
                candidate_rows = chart_section.find_all(["li", "article", "div"], recursive=True)
                # Count unique playlist positions
                positions = set()
                for row in candidate_rows:
                    for t in row.find_all(string=True):
                        stripped = t.strip()
                        if stripped.isdigit():
                            pos_num = int(stripped)
                            if pos_num > 0 and pos_num < 10000:  # Reasonable position range
                                positions.add(pos_num)
                            break
                playlists_loaded = len(positions)
                print(f"  Scroll {scroll_attempts}: Loaded {playlists_loaded} playlists so far...")

            # Check if we've reached the end
            new_height = driver.execute_script("return document.body.scrollHeight")
            if new_height == last_height:
                print("  Reached end of page.")
                break
            last_height = new_height
            scroll_attempts += 1

            if playlists_loaded >= min_playlists:
                print("  Target reached!")
                break

        # Get final HTML
        return BeautifulSoup(driver.page_source, "html.parser")
    finally:
        driver.quit()


def extract_playlists(soup: BeautifulSoup):
    """
    Extract playlist position, name, and curator from the Top-Playlists chart.
    IMPORTANT:
    - The exact HTML structure and class names may change.
    - You might need to adapt the CSS selectors below using your browser dev tools.
    """
    playlists = []
    seen = set()  # Track seen playlists to avoid duplicates

    # This is the critical part: find the container that holds the chart entries.
    # Apple usually uses <li> or <tr>-like elements for each chart row.
    #
    # Strategy:
    # 1. Look for elements that repeat for each playlist (e.g. li, article, div).
    # 2. Inside each item, find:
    #    - position number
    #    - playlist name
    #    - curator/owner
    #
    # Below is a generic version that you should tweak based on the actual HTML.
    # Example: assume each playlist is inside a <li> within a section that contains "Top-Playlists"

    chart_section = None
    for section in soup.find_all(["section", "main", "div"]):
        if section.get_text(strip=True).startswith("Top-Playlists"):
            chart_section = section
            break

    if chart_section is None:
        print("Could not find the Top-Playlists section. Check and adapt selectors.")
        return playlists

    # Try several possible row tags; Apple might use <li>, <article>, or <div role="row">
    candidate_rows = chart_section.find_all(["li", "article", "div"], recursive=True)

    for row in candidate_rows:
        # Heuristic: row must contain a number + playlist name + curator-like string
        # To keep it simple, we look for:
        #   - a number (position)
        #   - at least one link (playlist name)
        #   - some trailing text that looks like curator

        links = row.find_all("a")
        if not links:
            continue

        # Extract playlist name from the first link
        playlist_name = links[0].get_text(strip=True)
        if not playlist_name:
            continue

        # Try to find position: a small isolated integer somewhere in the row
        position_tag = None
        for t in row.find_all(string=True):
            stripped = t.strip()
            if stripped.isdigit():
                position_tag = stripped
                break

        if not position_tag:
            continue

        position = int(position_tag)

        # Curator: often appears as a separate small text after the name
        # We try to get a short text near the end that is not equal to playlist name.
        curator = None
        # Collect all text nodes (excluding scripts/styles)
        text_nodes = [
            t.strip()
            for t in row.stripped_strings
            if t.strip() and t.strip() != playlist_name and not t.strip().isdigit()
        ]

        if text_nodes:
            # Heuristic: last non-empty text that isn't the playlist name is likely the curator
            curator = text_nodes[-1]
        else:
            curator = ""

        # Create a unique key to avoid duplicates
        # Use position + playlist_name to remove duplicate entries
        key = (position, playlist_name)

        # If we've seen this position+name combo, update with better curator if available
        if key in seen:
            # Update if new curator is better
            # Prefer curator that matches the playlist name keywords
            existing = next((p for p in playlists if p["position"] == position and p["playlist_name"] == playlist_name), None)
            if existing:
                new_score = len(curator) if curator else 0
                old_score = len(existing.get("curator", "")) if existing.get("curator") else 0

                # Boost score if curator matches playlist keywords
                for keyword in playlist_name.lower().split():
                    if keyword in curator.lower() and len(keyword) > 2:
                        new_score += 5
                    if keyword in existing.get("curator", "").lower() and len(keyword) > 2:
                        old_score += 5

                if new_score > old_score:
                    existing["curator"] = curator
        else:
            seen.add(key)
            playlists.append(
                {
                    "position": position,
                    "playlist_name": playlist_name,
                    "curator": curator,
                }
            )

    # Sort by numeric position just in case
    playlists.sort(key=lambda x: x["position"])
    return playlists


def save_to_csv(playlists, filename="Apple_songs_webscrapped.csv"):
    """Save playlist data to a CSV file."""
    fieldnames = ["position", "playlist_name", "curator"]
    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for pl in playlists:
            writer.writerow(pl)


def main():
    print("Downloading page...")
    soup = fetch_page_with_selenium(URL, min_playlists=200)
    print("Extracting playlists...")
    playlists = extract_playlists(soup)
    print(f"Found {len(playlists)} playlists.")
    for pl in playlists:
        print(f"{pl['position']:>3} | {pl['playlist_name']} | {pl['curator']}")
    save_to_csv(playlists)
    print('Saved to "Apple_songs_webscrapped.csv"')


if __name__ == "__main__":
    main()
