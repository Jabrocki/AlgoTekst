from bs4 import BeautifulSoup
import requests
from urllib.parse import urljoin
import time
import os


HEADERS = {
    "User-Agent": "MushroomScraper/1.0 (kontakt: bartek.gryn12@gmail.com)"
}

BASE_WIKI_URL = "https://pl.wikipedia.org/wiki/"
API_BASE = "https://pl.wikipedia.org/api/rest_v1/page/html/"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(BASE_DIR, "grzyby")
os.makedirs(OUTPUT_DIR, exist_ok=True)


def fetch_with_retry(url, headers, retries=3):
    for attempt in range(retries):
        try:
            res = requests.get(url, headers=headers, timeout=10)

            if res.status_code == 200:
                return res

            print(f"Status {res.status_code}, próba {attempt + 1}")

        except requests.exceptions.RequestException as e:
            print(f"Błąd: {e}, próba {attempt + 1}")

        time.sleep(2)

    return None


def get_mushroom_links():
    url = f"{API_BASE}Grzyby_jadalne"

    res = requests.get(url, headers=HEADERS)
    print(f"Status: {res.status_code}")

    soup = BeautifulSoup(res.text, "lxml")

    mushroom_dict = {}

    uls = soup.find_all("ul")[:4]

    for ul in uls:
        for li in ul.find_all("li"):
            link = li.find("a")

            if not link or not link.get("href"):
                continue

            if link.get("title") and "strona nie istnieje" in link["title"]:
                continue

            href = link.get("href")

            if "redlink" in href:
                continue

            if href.startswith("./"):
                href = href[2:]

            full_url = urljoin(BASE_WIKI_URL, href)

            title = full_url.split("/wiki/")[1]
            api_url = f"{API_BASE}{title}"

            mushroom_name = link.get_text(strip=True)
            mushroom_dict[mushroom_name] = api_url

    print(f"\nZnaleziono {len(mushroom_dict)} pozycji\n")
    return mushroom_dict


def parse_to_markdown(html):
    soup = BeautifulSoup(html, "lxml")

    for tag in soup.select("sup.reference, table, style"):
        tag.decompose()

    content = []

    for tag in soup.find_all(["h1", "h2", "h3", "p"]):
        text = tag.get_text(strip=True)

        if not text:
            continue

        if tag.name == "h1":
            content.append(f"# {text}")
        elif tag.name == "h2":
            content.append(f"\n## {text}")
        elif tag.name == "h3":
            content.append(f"\n### {text}")
        elif tag.name == "p":
            content.append(text)

    return "\n\n".join(content)


def save_markdown(name, markdown):
    filename = name.replace(" ", "_").replace("/", "_") + ".md"
    filepath = os.path.join(OUTPUT_DIR, filename)

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(markdown)

    return filename


def main():
    mushroom_dict = get_mushroom_links()

    for i, (name, api_url) in enumerate(mushroom_dict.items(), 1):
        try:
            res = fetch_with_retry(api_url, HEADERS)

            if res is None:
                print(f"pominięto: {name}")
                continue

            markdown = parse_to_markdown(res.text)

            filename = save_markdown(name, markdown)

            print(f"{i}. zapisano: {filename}")

            time.sleep(1)

        except Exception as e:
            print(f"Błąd przy {name}: {e}")


if __name__ == "__main__":
    main()