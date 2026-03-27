import requests
from bs4 import BeautifulSoup
import re
import time
import os


# ekstrakcja danych
def get_all_sections(soup):
    full_markdown_text = ""

    # wyciągnięcie głównego kontenera z artykułu
    main_container = soup.find('div', class_=re.compile(r'fungus2__description|article-content'))
    search_area = main_container if main_container else soup

    # pobranie wszystkich h2 (nagłówki poszczególnych sekcji w opisie grzyba na stronie)
    headers = search_area.find_all('h2')

    # jeśli nie ma nagłówków to robimy po prostu jedną sekcję "Opis ogólny"
    if not headers:
        paragraphs = search_area.find_all('p')
        if paragraphs:
            full_markdown_text += "## Opis ogólny\n"
            for p in paragraphs:
                raw_text = p.get_text(separator=" ", strip=True)
                clean_text = re.sub(r'\s+', ' ', raw_text)
                if clean_text:
                    full_markdown_text += f"{clean_text}\n\n"
        else:
            return "Brak opisu tekstowego na tej stronie."

    # dalsza logika dla wersji gdzie są nagłówki (chyba wszystkie strony)
    else:
        for h2 in headers:
            title = h2.get_text(strip=True)

            # pominięcie nieistotnych nagłówków z boku / na dole strony
            if title.lower() in ["zobacz również", "tagi", "zostaw komentarz"]:
                continue

            full_markdown_text += f"## {title}\n"

            # szukanie najwyższego elementu w którym zamknięte jest h2 (na wypadek nastackowanych div'ów)
            current_element = h2
            while current_element.parent and current_element.parent != search_area:
                if current_element.name == 'body':
                    break
                current_element = current_element.parent

            # przeszukanie sąsiadów kontenera z nagłówkiem
            for sibling in current_element.find_next_siblings():
                # koniec iteracji pętli jeśli znajdziemy nagłówek (h2)
                if sibling.name == 'h2' or sibling.find('h2'):
                    break

                # zbieranie tekstu z sąsiada nagłówka (najczęściej bloku <p> z zapobiegnięciem zjadania spacji)
                raw_text = sibling.get_text(separator=" ", strip=True)
                # usunięcie wielokrotnych spacji
                clean_text = re.sub(r'\s+', ' ', raw_text)

                # dodanie czystego tekstu do Markdowna
                if clean_text:
                    full_markdown_text += f"{clean_text}\n\n"

    return full_markdown_text.strip()


def get_active_months(soup):
    month_names = ["Styczeń", "Luty", "Marzec", "Kwiecień", "Maj", "Czerwiec",
                   "Lipiec", "Sierpień", "Wrzesień", "Październik", "Listopad", "Grudzień"]
    active_months = []

    # szukanie sekcji z miesiącami
    container = soup.find('div', class_='fungus2__time__items')
    if container:
        tiles = container.find_all('div', class_='fungus2__time__item')
        # przejście dwunastu kafelków w poszukiwaniu tych które mają is-active
        for index, tile in enumerate(tiles):
            if 'is-active' in tile.get('class', []):
                active_months.append(month_names[index])

    return ", ".join(active_months) if active_months else "Brak danych"


# jeśli nie istnieje, tworzymy folder mushroom_data na dane o grzybach
output_folder = "mushroom_data"
os.makedirs(output_folder, exist_ok=True)

print("Fetching sitemap and extracting links...")
sitemap_url = "https://www.ekologia.pl/grzyby-sitemap.xml"
response = requests.get(sitemap_url)
soup_xml = BeautifulSoup(response.content, "xml")

# ekstrakcja linków prowadzących do grzybów
all_links = []
for url_tag in soup_xml.find_all("url"):
    loc_tag = url_tag.find("loc")
    if loc_tag and "ekologia.pl/grzyby/" in loc_tag.text:
        all_links.append(loc_tag.text)

print(f"Found {len(all_links)} mushrooms to scrape!")
print("Starting the scraper (testing with the first 5)...\n")

# testowy zbiór linków (do sprawdzania poprawności działania bez konieczności scrapowania ponad 450 linków)
test_links = all_links

# główna pętla scrapera
for index, link in enumerate(test_links, 1):
    print(f"[{index}/{len(test_links)}] Scraping: {link}")

    try:
        resp = requests.get(link)
        soup = BeautifulSoup(resp.content, "html.parser")

        # wyciąganie nazwy grzyba z nagłówka h1
        h1_tag = soup.find("h1")
        mushroom_name = h1_tag.text.strip() if h1_tag else "Unknown_Mushroom"

        # wywołanie funkcji scrapujących zdefiniowanych wcześniej
        season = get_active_months(soup)
        all_sections_text = get_all_sections(soup)

        # stworzenie pliku markdown
        markdown_template = f"""---
name: {mushroom_name}
season: {season}
source: {link}
---

# {mushroom_name}

{all_sections_text}
"""

        # dwie opcje nazewnictwa plików

        # opcja 1 - polska_nazwa(łacińska_nazwa).md
        # safe_file_name = f"{mushroom_name.replace(' ', '_').replace('/', '_')}.md"

        # opcja 2 - polska_nazwa.md
        polish_name_only = mushroom_name.split('(')[0].strip()
        safe_file_name = f"{polish_name_only.replace(' ', '_').replace('/', '_')}.md"

        # zapis do pliku
        save_path = os.path.join(output_folder, safe_file_name)
        with open(save_path, "w", encoding="utf-8") as file:
            file.write(markdown_template)

        print(f" -> Saved: {safe_file_name}")

    except Exception as e:
        print(f" -> Error while scraping {link}: {e}")

    # pauza żeby nie obciążyć serwera (zgodnie z etyką :) )
    time.sleep(2)

print(f"\nFinished! Check the '{output_folder}' directory.")