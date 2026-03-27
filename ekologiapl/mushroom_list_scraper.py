import requests
from bs4 import BeautifulSoup
import time

sitemap_url = "https://www.ekologia.pl/grzyby-sitemap.xml"

print("Pobieram sitemapę...")
response = requests.get(sitemap_url)

soup = BeautifulSoup(response.content, "xml")

mushroom_links = []
for url_tag in soup.find_all("url"):
    loc_tag = url_tag.find("loc")
    if loc_tag:
        link = loc_tag.text
        if "ekologia.pl/grzyby/" in link:
            mushroom_links.append(link)

print(f"Znaleziono {len(mushroom_links)} linków do grzybów.")
print("-" * 40)
print("Pierwsze 5 linków z listy:")

for link in mushroom_links[:5]:
    print(link)