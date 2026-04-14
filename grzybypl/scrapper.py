from bs4 import BeautifulSoup, Tag
from bs4.element import NavigableString
import requests
import os

from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
from threading import Lock

# Starting page https://grzyby.pl/atlas-grzybow-przyrodnika.htm
# Or maybe this is better https://grzyby.pl/system.htm

visited_lock = Lock()


def get_polish_name(soup: BeautifulSoup) -> str | None:
    div = soup.select_one("div.nazwy-narodowe")
    if div is None:
        return None

    first_text = div.find(string=True, recursive=False)
    if first_text is None:
        return None

    return str(first_text).strip().rstrip(",").capitalize()


def get_links(soup: BeautifulSoup, visited: set):
    links = soup.select('a[href^="/gatunki/"]')
    new_links_list = []
    for link in links:
        href = link.get("href")
        if href is None:
            continue
        clean_href = "https://grzyby.pl" + str(href).split("#")[0]

        with visited_lock:
            if clean_href not in visited:
                visited.add(clean_href)
                new_links_list.append(clean_href)

    return new_links_list


def get_latin_name(soup: BeautifulSoup) -> str | None:
    el = soup.select_one("h1 .name-latin")
    if el is None:
        return None
    return " ".join(el.get_text(" ", strip=True).split())


def html_to_markdown_text(block: Tag) -> str:
    block = BeautifulSoup(str(block), "html.parser")

    for b in block.find_all("b"):
        b.replace_with(NavigableString(f"**{b.get_text(' ', strip=True)}**"))

    text = block.get_text(" ", strip=True)
    return " ".join(text.split())


def get_polish_blocks(section: Tag):
    return [
        div
        for div in section.select("div.tresc-tekst")
        if div.select_one(".eng") is None
    ]


def scrapp_section(blocks: list[Tag], file_path: str):
    for block in blocks:
        text = html_to_markdown_text(block)
        with open(file_path, "a", encoding="utf-8") as file:
            file.write(f"\n{text}\n\n")


def scrap_from_url_grzybypl(url: str, visited: set[str]) -> list[str]:
    response = requests.get(url)
    response.encoding = response.apparent_encoding
    soup = BeautifulSoup(response.text, "html.parser")

    # zbierz linki do dalszego scrapowania
    new_links = get_links(soup, visited)

    latin_name = get_latin_name(soup)
    if latin_name is None:
        return new_links

    polish_name = get_polish_name(soup)
    if polish_name is None:
        return new_links

    section_titles = soup.select("div.opis-margines")
    sections = soup.select("div.opis-druga-col")

    if not section_titles or not sections:
        return new_links

    collected_sections: list[tuple[str, list[str]]] = []

    for title_div, section_div in zip(section_titles, sections):
        title_tag = title_div.select_one("h2")
        if title_tag is None:
            continue

        blocks = get_polish_blocks(section_div)
        if not blocks:
            continue

        title = (
            " ".join(title_tag.get_text(" ", strip=True).split())
            .replace('"', "")
            .replace("🛒", "")
            .strip()
            .capitalize()
        )

        if not title:
            continue

        texts = []
        for block in blocks:
            text = html_to_markdown_text(block)
            if text:
                texts.append(text)

        if texts:
            collected_sections.append((title, texts))

    if (
        len(collected_sections) <= 2
        and len("".join(text for _, texts in collected_sections for text in texts))
        <= 500
    ):
        return new_links

    mushroom_filename = latin_name.replace(" ", "_").lower() + "_grzybypl.md"
    mushroom_path = os.path.join(os.curdir, "data", mushroom_filename)

    with open(mushroom_path, "w", encoding="utf-8") as file:
        file.write("---\n")
        file.write(f"latin_name: {latin_name}\n")
        file.write(f"polish_name: {polish_name}\n")
        file.write(f"source: {url}\n")
        file.write("---\n\n")
        file.write(f"# {polish_name}\n")

        for title, texts in collected_sections:
            file.write(f"\n## {title}\n")
            for text in texts:
                file.write(f"\n{text}\n")

    print(polish_name)

    return new_links


def crawl(start_urls: list[str], max_workers: int = 10) -> None:
    visited: set[str] = set(start_urls)

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(scrap_from_url_grzybypl, url, visited) for url in start_urls
        }

        while futures:
            done, futures = wait(futures, return_when=FIRST_COMPLETED)

            for future in done:
                try:
                    new_links = future.result()
                except Exception as e:
                    print(f"[ERROR] worker crashed: {e}")
                    continue

                for link in new_links:
                    futures.add(executor.submit(scrap_from_url_grzybypl, link, visited))


if __name__ == "__main__":
    data_dir = os.path.join(os.curdir, "data")
    os.makedirs(data_dir, exist_ok=True)
    start_urls = [
        "https://grzyby.pl/system.htm",
        "https://grzyby.pl/atlas-grzybow-przyrodnika.htm",
    ]
    crawl(start_urls, max_workers=32)
