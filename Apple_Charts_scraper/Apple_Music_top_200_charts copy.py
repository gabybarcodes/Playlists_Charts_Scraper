import csv
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup

# URL of the Apple Music Top Playlists page
URL = "https://music.apple.com/de/new/top-charts/playlists"


def scroll_page(driver, scroll_count=4):
    """Scroll within the chart container to load more content."""
    # Try to find the scrollable chart container
    try:
        # Wait for the page to be interactive
        time.sleep(2)

        # Try to find and scroll the main content area
        for i in range(scroll_count):
            print(f"Scrolling {i + 1}/{scroll_count}...")

            # Scroll the entire page
            driver.execute_script(
                """
                var scrollSpeed = 500;
                var scrolling = setInterval(function() {
                    window.scrollBy(0, scrollSpeed);
                }, 100);
                setTimeout(function() {
                    clearInterval(scrolling);
                }, 3000);
                """
            )

            time.sleep(4)

            # Try clicking "load more" buttons if they exist
            try:
                load_more_buttons = driver.find_elements(By.XPATH, "//button[contains(text(), 'More') or contains(text(), 'Load')]")
                for button in load_more_buttons:
                    try:
                        button.click()
                        time.sleep(2)
                    except Exception:
                        pass
            except Exception:
                pass

    except Exception as e:
        print(f"Error during scrolling: {e}")


def extract_playlists_from_page(driver):
    """Extract all playlists from the loaded page using BeautifulSoup."""
    # Get the page source
    page_html = driver.page_source
    soup = BeautifulSoup(page_html, "html.parser")

    playlists = []
    seen = set()

    # Find the chart section
    chart_section = None
    for section in soup.find_all(["section", "main", "div"]):
        section_text = section.get_text(strip=True)
        if section_text.startswith("Top-Playlists") or "Top-Playlists" in section_text:
            chart_section = section
            break

    if chart_section is None:
        print("Could not find the Top-Playlists section.")
        return playlists

    # Find all playlist rows
    candidate_rows = chart_section.find_all(["li", "article", "div"], recursive=True)

    for row in candidate_rows:
        links = row.find_all("a")
        if not links:
            continue

        # Extract playlist name from the first link
        playlist_name = links[0].get_text(strip=True)
        if not playlist_name:
            continue

        # Try to find position (a number at the start of the row)
        position_tag = None
        for t in row.find_all(string=True):
            stripped = t.strip()
            if stripped.isdigit():
                position_tag = stripped
                break

        if not position_tag:
            continue

        position = int(position_tag)

        # Extract curator (text from the row)
        curator = ""
        text_nodes = [
            t.strip()
            for t in row.stripped_strings
            if t.strip() and t.strip() != playlist_name and not t.strip().isdigit()
        ]

        if text_nodes:
            curator = text_nodes[-1]

        # Create unique key using position + playlist_name
        key = (position, playlist_name)

        if key in seen:
            # Update with better curator if available
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

    # Sort by numeric position
    playlists.sort(key=lambda x: x["position"])
    return playlists


def save_to_csv(playlists, filename="apple_music_top_200_playlists.csv"):
    """Save playlist data to a CSV file."""
    fieldnames = ["position", "playlist_name", "curator"]
    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for pl in playlists:
            writer.writerow(pl)


def main():
    # Set up Chrome options
    chrome_options = Options()
    # Uncomment the line below to run headless (without opening browser window)
    # chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")

    print("Starting Selenium WebDriver...")
    driver = webdriver.Chrome(options=chrome_options)

    try:
        print(f"Loading page: {URL}")
        driver.get(URL)

        # Wait for initial content to load
        print("Waiting for page to load...")
        time.sleep(3)

        # Scroll 4 times to load more playlists
        scroll_page(driver, scroll_count=4)

        print("Extracting playlists...")
        playlists = extract_playlists_from_page(driver)

        print(f"Found {len(playlists)} playlists.")
        for pl in playlists:
            print(f"{pl['position']:>3} | {pl['playlist_name']} | {pl['curator']}")

        save_to_csv(playlists)
        print('Saved to "apple_music_top_200_playlists.csv"')

    finally:
        driver.quit()


if __name__ == "__main__":
    main()
