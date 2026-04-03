import os
import re
import time
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

def sanitize_filename(filename):
    pl_do_en = str.maketrans("ąćęłńóśźżĄĆĘŁŃÓŚŹŻ", "acelnoszzACELNOSZZ")
    clean = filename.translate(pl_do_en)
    clean = re.sub(r'[\\/*?:"<>|]', "", clean).strip()
    clean = re.sub(r'[\s\-]+', '_', clean)
    
    return clean.lower()[:100]

def format_description(text):
    lines = [line.strip() for line in text.split('\n') if line.strip()]

    # delete garbage
    start_index = 0
    for i, line in enumerate(lines):
        if line.lower() in ["podstawowe informacje", "opis"]:
            start_index = i
            break
            
    lines = lines[start_index:]


    glowne_naglowki = [
        "podstawowe informacje", "opis", "inne nazwy", 
        "kapelusz", "trzon", "hymenofor", "występowanie", "inne"
    ]
    puste_wartosci = ["brak", "brak opisu"]
    
    temp_lines = [] # sometimes there are empty categories
    
    for line in lines:
        if line.lower() in glowne_naglowki:
            temp_lines.append(f"\n## {line.capitalize()}")
            continue

        if line.lower() in puste_wartosci:
            if temp_lines and temp_lines[-1].endswith(":"):
                temp_lines.pop()
            continue

        temp_lines.append(line)

    final_lines = []
    for i, item in enumerate(temp_lines):
        if item.startswith("\n## "):
            if i == len(temp_lines) - 1 or temp_lines[i+1].startswith("\n## "):
                continue
        final_lines.append(item)

    wynik = "\n".join(final_lines)
    wynik = re.sub(r'\n{3,}', '\n\n', wynik)
    return wynik.strip()

def scrape_mushrooms_semi_auto(start_id, end_id):
    output_dir = "atlas_grzybow"
    os.makedirs(output_dir, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(viewport={'width': 1280, 'height': 800})
        page = context.new_page()

        print("loading...")
        page.goto("https://www.nagrzyby.pl/", wait_until="networkidle")


        print("start countdown...") #time to accept cookies and prepare the page
        
        for sekunda in range(8, 0, -1):
            print(f" {sekunda} ", end="\r")
            time.sleep(1)
        
        print("\n\nstarting...\n")

        for i in range(start_id, end_id + 1):
            url = f"https://www.nagrzyby.pl/atlas/{i}"
            print(f"downloading ID {i}...", end=" ")

            try:
                page.goto(url, wait_until="domcontentloaded", timeout=60000)
                time.sleep(2)

                soup = BeautifulSoup(page.content(), 'html.parser')

                name_tag = soup.find('h1')
                if not name_tag:
                    print("empty")
                    continue
                    
                mushroom_name = name_tag.get_text().strip()
                
                h2_tag = name_tag.find_next_sibling('h2')
                header_name = mushroom_name 
                
                if h2_tag:
                    i_tag = h2_tag.find('i')
                    if i_tag:
                        latin_name = i_tag.get_text().strip()
                        if latin_name: 
                            header_name = latin_name
                
                parent_div = name_tag.parent
                
                for trash in parent_div.find_all(['button', 'nav', 'svg']):
                    trash.decompose()
                
                name_tag.decompose()
                
                if h2_tag and h2_tag in parent_div.descendants:
                    h2_tag.decompose()
                
                raw_description = parent_div.get_text(separator="\n", strip=True)
                
                description = format_description(raw_description)

                safe_name = sanitize_filename(header_name)
                
                file_path = os.path.join(output_dir, f"{safe_name}_nagrzybypl.md")
                
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write("---\n")
                    f.write(f"name: {header_name}\n")
                    f.write(f"source: {url}\n")
                    f.write("---\n\n")
                    f.write(f"# {header_name}\n")
                    f.write(f"# {mushroom_name}\n\n")
                    
                    f.write(description)

                print(f"success -> {safe_name}_nagrzybypl.md")

            except Exception as e:
                print(f"error ID {i}: {e}")

        browser.close()
        print("\nZakończono pracę!")

if __name__ == "__main__":
    scrape_mushrooms_semi_auto(1,6000)