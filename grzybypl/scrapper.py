from bs4 import BeautifulSoup
import requests
import os


# Starting page https://grzyby.pl/atlas-grzybow-przyrodnika.htm
# Or maybe this is better https://grzyby.pl/system.htm
def get_polish_name(soup: BeautifulSoup) -> str | None:
    div = soup.select_one("div.nazwy-narodowe")
    if div is None:
        return None

    first_text = div.find(string=True, recursive=False)
    if first_text is None:
        return None

    return str(first_text).strip().rstrip(",").capitalize()


def get_links(soup: BeautifulSoup, queue: list[str], visited: set):
    links = soup.select('a[href^="/gatunki/"]')

    for link in links:
        href = link.get("href")
        if href is None:
            continue
        clean_href = "https://grzyby.pl" + str(href).split("#")[0]
        if clean_href not in visited:
            queue.append(clean_href)
            visited.add(clean_href)


def get_latin_name(soup: BeautifulSoup) -> str | None:
    el = soup.select_one("h1 .name-latin")
    if el is None:
        return None
    return " ".join(el.get_text(" ", strip=True).split())


def scrap_from_url_grzybypl(url: str, queue: list[str], visited: set):
    response = requests.get(url)
    response.encoding = response.apparent_encoding

    soup = BeautifulSoup(response.text, "html.parser")

    # Linki grzybów
    get_links(soup, queue, visited)

    # Sprawdz czy to gatunek lub forma i znajdz imiona - jezeli brak wyjdz
    latin_name = get_latin_name(soup)

    if latin_name is None:
        return

    if len(latin_name.split(" ")) < 2:
        return

    polish_name = get_polish_name(soup)
    if polish_name is None:
        return
    mushroom_filename = polish_name.replace(" ", "_") + "_grzybypl.md"
    mushroom_path = os.path.join(os.curdir, "data", mushroom_filename)
    mushroom_name = polish_name + f" ({latin_name})"

    with open(mushroom_path, "w", encoding="utf-8") as file:
        file.write("---\n")
        file.write(f"name: {mushroom_name}\n")
        file.write(f"source: {url}\n")
        file.write("---\n")
        file.write("\n")
        file.write(f"# {mushroom_name} \n")

    print(mushroom_name)
    print(mushroom_filename)

    section_titles = soup.select('div[class="opis-margines"]')
    sections = soup.select('div[class="opis-druga-col"]')

    for title_div, section_div in zip(section_titles, sections):
        title = title_div.select_one("h2")
        if title is None:
            continue
        title = (
            " ".join(title.get_text(" ", strip=True).split())
            .replace('"', "")
            .replace("!", "")
            .replace("🟢", "")
            .replace("🛒", "")
            .capitalize()
        )
        print(title)

    # print(sections)


scrap_from_url_grzybypl("https://grzyby.pl/gatunki/Boletus_edulis.htm", [], set())
