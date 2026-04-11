import requests
from bs4 import BeautifulSoup
import re
import time
import os
from concurrent.futures import ThreadPoolExecutor  # Dodane do wielowątkowości


def expand_latin_terms(text):
    mapping = {
        r'\bsubsp\.(?=\s|$)': 'subspecies',
        r'\bvar\.(?=\s|$)': 'varietas',
        r'\bsubvar\.(?=\s|$)': 'subvarietas',
        r'\bf\.(?=\s|$)': 'forma',
        r'\bsyn\.(?=\s|$)': 'synonymum',
        r'\bcoll\.(?=\s|$)': 'collectivum',
    }
    for pattern, full in mapping.items():
        text = re.sub(pattern, full, text, flags=re.IGNORECASE)
    return text


def clean_latin_name(raw_latin):
    latin = re.split(r'\(|&', raw_latin)[0]
    latin = expand_latin_terms(latin)
    latin = re.sub(r'\b[A-Z][a-z]*\.', '', latin)
    latin = re.sub(r'\s+', ' ', latin).strip()
    return latin.strip(' ,.&(')


def get_all_sections(soup):
    full_md = ""
    main_container = soup.find('div', class_=re.compile(r'fungus2__description|article-content'))
    search_area = main_container if main_container else soup
    headers = search_area.find_all('h2')

    if not headers:
        paragraphs = search_area.find_all('p')
        for p in paragraphs:
            txt = re.sub(r'\s+', ' ', p.get_text(separator=" ", strip=True))
            if txt: full_md += f"{txt}\n\n"
    else:
        for h2 in headers:
            title = h2.get_text(strip=True)
            if title.lower() in ["zobacz również", "tagi", "zostaw komentarz"]: continue
            full_md += f"## {title}\n"

            curr = h2
            while curr.parent and curr.parent != search_area:
                if curr.name == 'body': break
                curr = curr.parent

            for sib in curr.find_next_siblings():
                if sib.name == 'h2' or sib.find('h2'): break
                txt = re.sub(r'\s+', ' ', sib.get_text(separator=" ", strip=True))
                if txt: full_md += f"{txt}\n\n"
    return full_md.strip()

output_folder = "mushroom_data"
os.makedirs(output_folder, exist_ok=True)
MIN_CONTENT_LENGTH = 300
MAX_WORKERS = 10  # Liczba wątków

print("Pobieram sitemapę...")
try:
    response = requests.get("https://www.ekologia.pl/grzyby-sitemap.xml", timeout=15)
    soup_xml = BeautifulSoup(response.content, "xml")
    all_links = [url.loc.text for url in soup_xml.find_all("url") if "ekologia.pl/grzyby/" in url.loc.text]
except Exception as e:
    print(f"Błąd pobierania sitemapy: {e}")
    all_links = []

test_links = all_links

def scrap_mushroom(link):
    try:
        resp = requests.get(link, timeout=10)
        soup = BeautifulSoup(resp.content, "html.parser")
        h1_tag = soup.find("h1")
        h1 = h1_tag.text.strip() if h1_tag else ""

        if not h1: return

        polish_name = h1.split('(')[0].strip()
        match = re.search(r'\((.*?)\)', h1)
        latin_name = clean_latin_name(match.group(1)) if match else polish_name

        content = get_all_sections(soup)

        if len(content) < MIN_CONTENT_LENGTH:
            print(f"[-] POMINIĘTO (krótki): {polish_name}")
            return

        markdown = f"""---
latin_name: {latin_name}
polish_name: {polish_name}
source: {link}
---

# {latin_name}

## {polish_name}

{content}
"""
        file_base = latin_name.lower().replace(' ', '_')
        file_base = re.sub(r'[^a-z0-9_]', '', file_base)
        file_name = f"{file_base}_ekologiapl.md"

        with open(os.path.join(output_folder, file_name), "w", encoding="utf-8") as f:
            f.write(markdown)

        print(f"[+] ZAPISANO: {file_name}")

    except Exception as e:
        print(f"[!] Błąd: {link} -> {e}")


if __name__ == "__main__":
    print(f"Rozpoczynam pobieranie na {MAX_WORKERS} wątkach...")

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        executor.map(scrap_mushroom, test_links)

    print("\nGotowe! Pobrano wszystkie grzyby.")