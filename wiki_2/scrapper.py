import os
import pathlib
import asyncio
import httpx
from bs4 import BeautifulSoup
import re
import json

DATA_DIR = os.path.join(pathlib.Path(__file__).parent, "..", "data")
CURRENT_DATA_DIR = os.path.join(pathlib.Path(__file__).parent, "data")
os.makedirs(CURRENT_DATA_DIR, exist_ok=True)
WIKI_URL = "https://pl.wikipedia.org/w/api.php"


def get_latin_name(filename: str) -> str | None:
    name, _ = os.path.splitext(filename)
    return name.replace("_", " ").strip()


def clean_text(text: str) -> str:
    return re.sub(r"\[[^\]]*\]", "", text).strip()


async def save_article(article: dict):
    filename = f"{article['latin_name'].replace(' ', '_')}.md"
    filepath = os.path.join(CURRENT_DATA_DIR, filename)
    # Check content length to avoid saving empty articles
    content_length = sum(
        len(text) for section in article["content"] for text in section["content"]
    )
    if content_length <= 1000:
        print(
            f"Pomijam artykuł {article['latin_name']} z powodu zbyt krótkiej treści ({content_length} znaków)"
        )
        return

    print(f"Zapisuję artykuł: {article['latin_name']}")
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(f"""---
latin_name: {article['latin_name']}
polish_name: {article['polish_name']}
source: {article['source']}
---
""")

        f.write(f"# {article['polish_name']} \n")
        f.write(f"# {article['latin_name']} \n\n")

        for section in article["content"]:
            if section["title"] != article["polish_name"]:
                f.write(f"## {section['title']} \n\n")
            for paragraph in section["content"]:
                f.write(f"{paragraph}\n\n")


async def download_article(client: httpx.AsyncClient, result: dict):
    article_url = result.get("pl_wiki")
    params = {
        "action": "parse",
        "format": "json",
        "page": article_url.split("/wiki/")[-1],  # type: ignore
        "prop": "text",
        "disabletoc": 1,
    }
    article = {
        "polish_name": None,
        "latin_name": result.get("latin_name"),
        "source": article_url,
        "content": [],
    }
    try:
        response = await client.get(WIKI_URL, params=params, timeout=10)
        if response.status_code != 200:
            print(f"Błąd HTTP {response.status_code} dla: {result.get('latin_name')}")
            return

        data = response.json()
        page = str(data.get("parse", {}).get("text", {}).get("*", ""))
        soup = BeautifulSoup(page, "html.parser")

        polish_name = soup.find("div", "iboxt-1")  # type: ignore
        article["polish_name"] = (
            polish_name.text.strip() if polish_name else result.get("latin_name")
        )

        main_div = soup.find("div", "mw-parser-output")  # type: ignore
        if not main_div:
            print(f"Nie znaleziono tekstu dla: {result.get('latin_name')}")
            return

        children = main_div.contents
        current_section = {
            "title": (
                polish_name.text.strip() if polish_name else result.get("latin_name")
            ),
            "content": [],
        }
        for child in children:
            if child.name == "p":
                text = child.get_text().strip()
                if text:
                    current_section["content"].append(clean_text(text))
            elif child.name == "div" and "mw-heading" in child.get("class", []):
                article["content"].append(current_section)
                current_section = {
                    "title": clean_text(child.get_text().strip()),
                    "content": [],
                }

        article["content"].append(current_section)
        await save_article(article)

    except json.JSONDecodeError:
        print(f"Błąd kości JSON dla: {result.get('latin_name')}")
    except httpx.RequestError as e:
        print(f"Błąd sieciowy dla {result.get('latin_name')}: {e}")
    except Exception as e:
        print(f"Błąd dla {result.get('latin_name')}: {e}")


async def search_wikipedia(client: httpx.AsyncClient, latin_name: str):
    params = {
        "action": "query",
        "format": "json",
        "titles": latin_name,
        "redirects": 1,
    }

    try:
        response = await client.get(WIKI_URL, params=params, timeout=10)
        if response.status_code == 200:
            data = response.json()
            pages = data.get("query", {}).get("pages", {})

            for page_id, page_info in pages.items():
                if page_id != "-1":
                    title = page_info.get("title")
                    url_title = title.replace(" ", "_")
                    result = {
                        "latin_name": latin_name,
                        "title": title,
                        "pl_wiki": f"https://pl.wikipedia.org/wiki/{url_title}",
                    }
                    print(
                        f"Znaleziono artykuł dla: {latin_name} -> {result['pl_wiki']}"
                    )
                    await download_article(client, result)
                    return

            print(f"Nie znaleziono artykułu dla: {latin_name}")
        else:
            print(f"Błąd HTTP {response.status_code} dla: {latin_name}")

    except json.JSONDecodeError:
        print(f"Błąd JSON podczas wyszukiwania: {latin_name}")
    except httpx.RequestError as e:
        print(f"Błąd sieciowy podczas wyszukiwania {latin_name}: {e}")


async def main():
    headers = {"User-Agent": "Jan_Jabrocki/1.0 (kontakt: jjabrocki@gmail.com)"}

    async with httpx.AsyncClient(headers=headers) as client:
        filenames = [f for f in os.listdir(DATA_DIR) if not f.startswith(".")]
        batch_size = 10
        batches = [
            filenames[i : i + batch_size] for i in range(0, len(filenames), batch_size)
        ]

        for idx, batch in enumerate(batches):
            print(f"\n--- Paczka {idx + 1}/{len(batches)} ---")
            tasks = []
            for filename in batch:
                latin_name = get_latin_name(filename)
                if latin_name:
                    tasks.append(search_wikipedia(client, latin_name))

            await asyncio.gather(*tasks)

            if idx < len(batches) - 1:
                print("Przerwa 5s...")
                await asyncio.sleep(5.0)


if __name__ == "__main__":
    asyncio.run(main())
