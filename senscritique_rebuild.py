import re
import sys
import time
from playwright.sync_api import sync_playwright
import requests
from bs4 import BeautifulSoup
import requests
from pathlib import Path
import json
from playwright.sync_api import Browser, Locator
from random import randrange
import logging


logging.basicConfig(
    level=logging.DEBUG,
    format='%(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('app.log')
        ]
    )

USER_AGENT_PATH = Path(__file__).resolve().parent / "user_agent.json"
MOVIE_DATA_PATH = Path(__file__).resolve().parent / "movie_data.json"
MOVIE_ERROR_PATH = Path(__file__).resolve().parent / "movie_url_error.json"

if USER_AGENT_PATH.exists():
    with open(USER_AGENT_PATH, 'r') as f:
        USER_AGENT_LIST = json.load(f)
else:
    USER_AGENT_HTML = requests.get("https://raw.githubusercontent.com/tamimibrahim17/List-of-user-agents/master/Chrome.txt").content
    USER_AGENT_LIST = str(USER_AGENT_HTML).split("\\n")[3:-1]
    
    with open(USER_AGENT_PATH,'x') as f:
        json.dump(USER_AGENT_LIST, f)

if not MOVIE_DATA_PATH.exists():
    with open(MOVIE_DATA_PATH, 'x') as f:
        json.dump({}, f)

if not MOVIE_ERROR_PATH.exists():
    with open(MOVIE_DATA_PATH, 'x') as f:
        json.dump([], f)

COOKIES_TAG = "//button[@id='didomi-notice-agree-button']"
MOVIES_CONTAINER_TAG = "//div[@class='Section__Container-sc-1equfs8-0 jLWfQF']"
MAIN_PAGE_RATING_TAG = 'Rating__GlobalRating-sc-1rkvzid-5 cYgihZ Poster__GlobalRating-sc-1jujjag-7 iHxvoD globalRating'
DATA_CONTAINER_TAG = 'Text__SCText-sc-kgt5u3-0 Movie__Text-sc-1ilnh4x-1 hrLruZ ihArZu'
MOVIE_TITLE_CONTAINER_TAG = 'CoverProductInfos__Container-sc-cbcfd0-0 cBBjdC'
MOVIE_PAGE_RATING_CONTAINER_TAG = 'CoverProductInfos__WrapperRating-sc-cbcfd0-5 iStOFU'
UserAgentListLength = len(USER_AGENT_LIST)

def get_proxies():
    response = requests.get("https://free-proxy-list.net/").content
    soup = BeautifulSoup(response, 'lxml')

    proxy_list = []

    table = soup.find('table', 'table table-striped table-bordered')
    proxies = table.find_all('tr')

    for i in range(1, len(proxies) - 1):
        proxy = proxies[i].find_all('td')
        
        if proxy[6].text == 'yes':
            proxy_list.append(proxy[0].text)
        
        if len(proxy_list) == 4:
            break

    return(proxy_list)

def click_page_btn(btn_locator:Locator):
    btn_locator.element_handle()
    
    time.sleep(2)
    btn_locator.click()
    time.sleep(2)
    btn_locator.click()
    time.sleep(2)

def manage_js_movies_page(browser:Browser, page_url):
    logging.debug(f"traitement du js sur {page_url}")

    new_context = browser.new_context(user_agent=USER_AGENT_LIST[randrange(UserAgentListLength)])
    new_page = new_context.new_page()
    time.sleep(5)
    new_page.goto(page_url)

    time.sleep(5)
    new_page.click(COOKIES_TAG)
    
    container_boxes = new_page.locator('xpath=' + MOVIES_CONTAINER_TAG).element_handles()

    if len(container_boxes) == 3:
        while True:
            stream_boxes = new_page.locator("xpath=//div[@class='ProductListItem__Container-sc-ico7lo-0 hZLWXB']")
            stream_boxes.element_handles()[-1].scroll_into_view_if_needed()
            items_on_page = len(stream_boxes.element_handles())
            new_page.wait_for_timeout(10000) 
            items_on_page_after_scroll = len(stream_boxes.element_handles())

            if not items_on_page_after_scroll > items_on_page:
                break
        
        pageHTML = new_page.inner_html(MOVIES_CONTAINER_TAG + "[3]")
        new_page.close()

        logging.info(f"js traite avec succes sur {page_url}")

        return pageHTML

    else:
        while True:
            stream_boxes = new_page.locator("xpath=//div[@class='ProductListItem__Container-sc-ico7lo-0 hZLWXB']")
            container_boxes[3].scroll_into_view_if_needed()
            items_on_page = len(stream_boxes.element_handles())
            new_page.wait_for_timeout(15000) 
            items_on_page_after_scroll = len(stream_boxes.element_handles())

            if not items_on_page_after_scroll > items_on_page:
                break
            
        pageHTML = new_page.inner_html(MOVIES_CONTAINER_TAG + "[2]")
        new_page.close()

        logging.info(f"js traite avec succes sur {page_url}")

        return pageHTML

def get_best_movies(page_html):
    logging.debug('extraction des liens des meilleurs films')

    best_movies_links = []
    movies_soup = BeautifulSoup(page_html, 'lxml')
    movies_div = list(movies_soup.div.children)
    
    for movie_div in movies_div:
        movie_div_soup = BeautifulSoup(str(movie_div), 'lxml')

        try:
            rating_container = movie_div_soup.find('div', MAIN_PAGE_RATING_TAG)
            rating = float(rating_container.text)
            
            if rating > 7.4:
                movie_href = movie_div_soup.find('a', href=True)
                movie_link = 'https://www.senscritique.com' + movie_href['href']
                best_movies_links.append(movie_link)

        except AttributeError:
            movie_href = movie_div_soup.find('a', href=True)['href']
            logging.error(f'Pas de note pour {movie_href}')
        
    logging.info('Obtention des liens pour les films')

    return best_movies_links

def get_data_from_movie_page(moviePageURL):
    logging.info(f"Obtention des donnees sur {moviePageURL}")

    userAgent = {'User-Agent':USER_AGENT_LIST[randrange(UserAgentListLength)]}
    movie_page = requests.get(moviePageURL, headers=userAgent).content
    movie_soup = BeautifulSoup(movie_page, 'lxml')

    rating_value = movie_soup.find('div', MOVIE_PAGE_RATING_CONTAINER_TAG).text
    movie_title = movie_soup.find('div', MOVIE_TITLE_CONTAINER_TAG).contents[0].text
    dataText = movie_soup.find('div', DATA_CONTAINER_TAG).text
    
    noise = re.findall('Groupe', dataText)
    finalData = re.split('Genre.?|Casting|Pays d\'origine|Bande originale|Groupe', dataText)

    numberOfCategories = len(finalData)

    try:     
        if numberOfCategories > 3:
            basicIndex = 1
            gender = finalData[1].strip(' :').split(', ')
        else:
            basicIndex = 0
            gender = None

        if noise:    
            country = finalData[basicIndex + 3].strip(' : ').split(', ')
        else:    
            country = finalData[basicIndex + 2].strip(' : ').split(', ')
        
        firstPart = re.split('·', finalData[0])

        producerName = firstPart[0].split('de')[-1].strip().split(' et ')
        movieType = firstPart[0].split('de')[0].strip()
        duration = firstPart[1].strip()

        if len(firstPart) > 2:
            date = firstPart[2].strip()
        else:
            date = None

        casting = finalData[2].strip(" (acteurs principaux) : ").split(", ")

        logging.info(f"Donnees recuperees avec succes")

    except IndexError as e:
        logging.error('Une erreur est arrivée lors du traitement des donnees : ' + str(e))

        with open('movie_error_url.json', 'r') as f:
            url_error_list:list = json.load(f)     

        if moviePageURL not in url_error_list:
            url_error_list.append(moviePageURL)

        with open('movie_error_url.json', 'w') as f:
            json.dump(url_error_list, f) 

    else:
        return {
            movie_title : {
            'type': movieType,
            'producer(s)': producerName,
            'date': date,
            'duration': duration,
            'rating' : rating_value,
            'genre(s)': gender,
            'casting': casting,
            'country': country
            }
        }

def get_number_of_movies_on_the_db():
    with open(MOVIE_DATA_PATH, 'r') as f:
        movies_dict = json.load(f)
        film_number = len(list(movies_dict.keys()))

    return film_number

def main(page_start_index:int = 1, page_end_index:int = 228):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, slow_mo=50)
        context = browser.new_context(user_agent=USER_AGENT_LIST[randrange(UserAgentListLength)])
        page = context.new_page()
        page.goto('https://www.senscritique.com/films/sondages')
        page.click(COOKIES_TAG)
        
        for page_index in range(page_start_index, page_end_index):
            logging.debug(f"Lancement de la page {page_index}")

            movies_pages_links_list = []
            PAGE_CONTAINER_TAG = "//div[@class='Row__Container-sc-z5g0f4-0 ceKqRj Polls__StyledRow-sc-y3u0sq-3 fBZumj']"
            next_page_btn_tag = f"{PAGE_CONTAINER_TAG}/div/div/div[7]/div/nav/span[@data-testid='click-{page_index}']"
            
            btn_locator = page.locator(f"xpath={next_page_btn_tag}")
            btn_presence = btn_locator.count()

            if not btn_presence:
                ref_index = page_index
                
                while not btn_presence:
                    ref_index -= 1
                    custom_btn_tag = f"{PAGE_CONTAINER_TAG}/div/div/div[7]/div/nav/span[@data-testid='click-{ref_index}']"
                    btn_locator = page.locator(f"xpath={custom_btn_tag}")

                    time.sleep(2)
                    btn_presence = btn_locator.count()
                
                while ref_index != page_index + 1:
                    custom_btn_tag = f"{PAGE_CONTAINER_TAG}/div/div/div[7]/div/nav/span[@data-testid='click-{ref_index}']"
                    btn_locator = page.locator(f"xpath={custom_btn_tag}")

                    click_page_btn(btn_locator)
                    ref_index += 1
            
            else:
                click_page_btn(btn_locator)
            
            movie_container = page.inner_html("//div[@class='Polls__WrapperLists-sc-y3u0sq-7 hVtrGP']")
            soup = BeautifulSoup(movie_container, 'lxml')
            link_tags = soup.find_all('div', 'ListOverview__Container-sc-10et7ih-0 gDcYvA')

            for link_tag in link_tags:
                link_container = BeautifulSoup(str(link_tag), 'lxml').find('a')
                movies_page_link = link_container.get('href')
                movies_pages_links_list.append('https://www.senscritique.com' + movies_page_link)

            for each_page_link in movies_pages_links_list:
                movies_page_html = manage_js_movies_page(browser, each_page_link)
                best_movies_links = get_best_movies(movies_page_html)

                for movie_link in best_movies_links:
                    data = get_data_from_movie_page(movie_link)

                    if data:
                        with open(MOVIE_DATA_PATH, 'r') as f:
                            currentData:dict = json.load(f)            
                        
                        currentData.update(data)

                        with open(MOVIE_DATA_PATH, 'w') as f:
                            json.dump(currentData, f, indent=4)
        
        logging.info(f'Scraping bouclé avec succès à la page {page_index}')


if __name__ == '__main__':
    main()
    
 
