"""
Grab historical campaign data from makeship website.

Follows these steps:

1. Uses beautifulsoup to grab past campaign links from `./html/Past Campaigns _ Makeship.html`
2. Multiprocess past links through selenium to extract specific product information
    (plush_name, creator_name, n_sold, ended_on, %_funded, etc)
3. Store results in json file
"""

from bs4 import BeautifulSoup
from selenium import webdriver
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
import time
import json
from multiprocessing import Pool
from tqdm import tqdm
import sys


def load_driver(url, images=False):
    """Load selenium webdriver

    Args:
        url (str): landing page for the webdriver
        images (bool): whether the webdriver should load images

    Returns
        Selenium chrome webdriver"""
    option = webdriver.ChromeOptions()
    if not images:
        chrome_prefs = {}
        option.experimental_options["prefs"] = chrome_prefs
        chrome_prefs["profile.default_content_settings"] = {"images": 2}
        chrome_prefs["profile.managed_default_content_settings"] = {"images": 2}

    # Ignore logging warnings
    option.add_experimental_option("excludeSwitches", ["enable-logging"])

    driver = webdriver.Chrome(ChromeDriverManager().install(), chrome_options=option)
    driver.get(url)
    return driver


def get_product_info(link, driver):
    """
    Get product information

    Args:
        link (str): link to product
        driver: selenium driver to load website

    Returns:
        Product information in the following format

        {
            plush_name,
            creator_name,
            n_sold: ,
            ended_on,
            percent_funded,
            creator_link,
            plush_image
        }
    """
    driver.get(link)
    time.sleep(1)

    # For queries that return multiple elements, they need a
    # method of filtering down to the relevant element
    text_filter = lambda l, q: [x for x in l if q.lower() in x.text.lower()]

    plush_name = driver.find_element(
        By.XPATH,
        "//h5[@class='Typography__H5-sc-16m971g-4 ProductInfostyled__ProductTitle-sc-1xewy4m-3 dxzTkD chJkst']",
    ).text
    creator_name = text_filter(
        driver.find_elements(
            By.XPATH,
            "//a[@class='link__Link-hiz1lc-0 primary__Primary-cxhzpj-0 clKkwo nWCVV']",
        ),
        "By: ",
    )
    n_sold = text_filter(
        driver.find_elements(
            By.XPATH, "//p[@class='Typography__S2-sc-16m971g-7 edJYQc']"
        ),
        "sold",
    )
    ended_on = text_filter(
        driver.find_elements(
            By.XPATH,
            "//p[@class='Typography__S2-sc-16m971g-7 ProductInfostyled__EndDate-sc-1xewy4m-7 edJYQc ihKqxd']",
        ),
        "Ended:",
    )
    percent_funded = text_filter(
        driver.find_elements(
            By.XPATH, "//p[@class='Typography__Caption-sc-16m971g-11 bWSSaY']"
        ),
        "Funded",
    )
    creator_link = text_filter(
        driver.find_elements(
            By.XPATH,
            "//a[@class='link__Link-hiz1lc-0 primary__Primary-cxhzpj-0 clKkwo nWCVV']",
        ),
        "Click here",
    )
    plush_image = (
        driver.find_element(
            By.XPATH,
            "//div[@class='ImageGallery__MainImageContainer-sc-372mel-2 iivUGQ']",
        )
        .find_elements(By.TAG_NAME, "img")[-1]
        .get_attribute("src")
    )

    product_info = dict(
        plush_name=plush_name,
        creator_name=creator_name[0].text if creator_name else None,
        n_sold=n_sold[0].text if n_sold else None,
        ended_on=ended_on[0].text if ended_on else None,
        percent_funded=percent_funded[0].text if percent_funded else None,
        creator_link=creator_link[0].get_attribute("href") if creator_link else None,
        plush_image=plush_image,
    )
    return process_product_info(product_info)


def process_product_info(product_info):
    """
    Remove unnecessary str from product_info values.

    Arg
        product_info (dict): partial output of get_product_info

    Returns
        product_info with values stripped of unnecessary str
    """
    # strings to remove from values
    remove = dict(
        creator_name="By:", n_sold="sold", ended_on="Ended:", percent_funded="Funded"
    )

    for k, v in product_info.items():
        to_remove = remove.get(k)

        if to_remove and v is not None:
            v = v.replace(to_remove, "").strip()
            product_info[k] = v

    return product_info


def get_past_info(past_links):
    """Pipeline for getting past information via urls"""
    driver = load_driver("https://www.google.com/", True)

    past_products = []
    for link in tqdm(past_links):
        product_info = get_product_info(link, driver)
        product_info["url"] = link
        past_products.append(product_info)

    return past_products


def chunks(lst, n):
    """Yield successive n even-sized chunks from lst."""
    chunksize = len(lst) // n
    for i in range(n):
        start = i * chunksize
        if i + 1 == n:
            yield lst[start:]
        else:
            yield lst[start : start + chunksize]


def run(N_CPUS):
    """Starter function that multiprocesses the collection of past info"""

    # 1. Get links for past url products
    with open("./html/Past Campaigns _ Makeship.html", encoding="utf8") as f:
        soup = BeautifulSoup(f, "html.parser")
    products = soup.find_all("div", {"data-gtm-name": "product-card-container"})
    past_links = [product.find("a")["href"] for product in products]

    # 2. Chunk and multiprocess links
    chunked_links = chunks(past_links, N_CPUS)
    with Pool(N_CPUS) as pool:
        past_products = pool.map(get_past_info, chunked_links)

    # 3. Combine results and write json
    combined_results = [inner for outer in past_products for inner in outer]
    with open("./out/past_product_info.json", "w") as f:
        json.dump(combined_results, f)


if __name__ == "__main__":
    N_CPUS = int(sys.argv[1])
    run(N_CPUS)
