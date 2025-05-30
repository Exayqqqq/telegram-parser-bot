
import asyncio
import os
import re
import aiohttp
from bs4 import BeautifulSoup

proxy_host = '127.0.0.1'
proxy_port = '60000'
username = '89079454-zone-custom-region-IT'
password = 'mC9WjsNg'

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'
}

MAX_NEW_LINKS = 200
LINKS_FILE = "parser_links.txt"
SEEN_FILE = "seen_links.txt"

lock = asyncio.Lock()

async def check_reviews(session, ad_url):
    try:
        async with session.get(ad_url, headers=headers, proxy=f"http://{username}:{password}@{proxy_host}:{proxy_port}") as response:
            response.raise_for_status()
            response_text = await response.text()
            soup = BeautifulSoup(response_text, "html.parser")
            review_tag = soup.find("p", class_="index-module_sbt-text-atom__ifYVU index-module_token-body__erqqS index-module_size-small__qLPdh index-module_weight-book__kP2zY index-module_message__QlUVY")
            return review_tag is not None and "Nessuna recensione" in review_tag.text
    except Exception as e:
        print(f"[ERROR in check_reviews] {ad_url}: {e}")
        return False

async def check_ads(session, ad_url, max_ads_allowed=5):
    try:
        async with session.get(ad_url, headers=headers, proxy=f"http://{username}:{password}@{proxy_host}:{proxy_port}") as response:
            html = await response.text()
            soup = BeautifulSoup(html, "html.parser")
            user_link_tag = soup.select_one("h6.UserName_name__ZmLy8 a")
            if not user_link_tag:
                return None, False
            user_url = "https://www.subito.it" + user_link_tag['href']
            async with session.get(user_url, headers=headers, proxy=f"http://{username}:{password}@{proxy_host}:{proxy_port}") as user_response:
                user_html = await user_response.text()
                user_soup = BeautifulSoup(user_html, "html.parser")
                box = user_soup.select_one("div.UserData_trust_info_box__jkk6c")
                if not box:
                    return user_url, False
                p_tags = box.find_all("p")
                for i, p_tag in enumerate(p_tags):
                    if p_tag.get_text(strip=True) == "Annunci pubblicati":
                        if i == 0:
                            return user_url, False
                        prev_p = p_tags[i-1]
                        if "body-text" in prev_p.get("class", []) and "semibold" in prev_p.get("class", []) and "small" in prev_p.get("class", []):
                            ads_count_text = prev_p.get_text(strip=True)
                            ads_count = int(re.search(r'\d+', ads_count_text).group())
                            return user_url, ads_count <= max_ads_allowed
                return user_url, False
    except Exception as e:
        print(f"[ERROR in check_ads] {ad_url}: {e}")
        return None, False

async def fetch_ads(session, url, seen_links, seen_users, user_seen_file, new_links_collected):
    try:
        async with session.get(url, headers=headers, proxy=f"http://{username}:{password}@{proxy_host}:{proxy_port}") as response:
            html = await response.text()
            soup = BeautifulSoup(html, "html.parser")
            ads = soup.find_all("div", class_="SmallCard-module_card__3hfzu")
            for ad in ads:
                async with lock:
                    if new_links_collected[0] >= MAX_NEW_LINKS:
                        return
                link_tag = ad.find("a", class_="SmallCard-module_link__hOkzY")
                link = link_tag['href'] if link_tag else None
                if not link:
                    continue
                async with lock:
                    if link in seen_links:
                        continue
                reviews_ok = await check_reviews(session, link)
                user_url, ads_ok = await check_ads(session, link)
                if not user_url:
                    continue
                async with lock:
                    if user_url in seen_users:
                        continue
                if reviews_ok and ads_ok:
                    async with lock:
                        with open(user_seen_file, "a", encoding="utf-8") as f_user:
                            f_user.write(link + "\n")
                        seen_links.add(link)
                        seen_users.add(user_url)
                        new_links_collected[0] += 1
                        yield link
    except Exception as e:
        print(f"[ERROR in fetch_ads] {url}: {e}")

async def process_category(session, base_url, seen_links, seen_users, user_seen_file, new_links_collected):
    urls = [base_url] + [f'{base_url}&o={i}' for i in range(2, 15)]
    for url in urls:
        async with lock:
            if new_links_collected[0] >= MAX_NEW_LINKS:
                return
        async for link in fetch_ads(session, url, seen_links, seen_users, user_seen_file, new_links_collected):
            yield link

async def run_parser_for_user(user_id):
    allowed_users = {"123456789", "987654321"}  # добавь свой Telegram ID
    if str(user_id) not in allowed_users:
        print(f"[ACCESS DENIED] User {user_id} is not authorized.")
        return

    user_seen_file = f"seen_links_{user_id}.txt"
    if not os.path.exists(user_seen_file):
        open(user_seen_file, "w", encoding="utf-8").close()

    with open(user_seen_file, "r", encoding="utf-8") as f_seen:
        seen_links = {line.strip() for line in f_seen if line.strip()}

    seen_users = set()
    new_links_collected = [0]

    categories = [
        'https://www.subito.it/annunci-italia/vendita/sport/?order=datedesc&ps=25',
        'https://www.subito.it/annunci-italia/vendita/bambini-giocattoli/?order=datedesc&ps=25',
        'https://www.subito.it/annunci-italia/vendita/fotografia/?shp=true'
    ]

    async with aiohttp.ClientSession() as session:
        for category in categories:
            async for link in process_category(session, category, seen_links, seen_users, user_seen_file, new_links_collected):
                yield link
