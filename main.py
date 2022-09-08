import requests
from tqdm import tqdm
from bs4 import BeautifulSoup
from deep_translator import GoogleTranslator
import vk
import pandas as pd
from random import randint
import schedule
from time import sleep
from os import environ

latest_post_link_file = open("/home/ubuntu/latest_post_link.txt", "r")
latest_post_link = latest_post_link_file.readline().strip()
latest_post_link_file.close()
if not latest_post_link:
    latest_post_link = ""

hypebeast_link = "https://hypebeast.com/footwear"
track_ids = pd.read_csv('tracks_id.csv')
access_token = environ['TOKEN']
session = vk.API(access_token=access_token, v='5.95')
group_id = 215478637


def get_random_tracks_id(count):
    global track_ids
    ids = []
    for i in range(count):
        rand_pos = randint(0, 9999)
        ids.append('audio' + track_ids.iloc[rand_pos]['0'])
    return ids


def get_images_links(post_html):
    content = post_html.find_all('div',
                                 'post-gallery-container small inner-media')
    if not content:
        content = post_html.find_all("div", "post-gallery-container portrait inner-media")
        if not content:
            print("No photos found")
            return []
        content = content[0]
        pages = content.contents[1].contents[1].contents[1].contents[1].contents[1].contents[1].contents
        pages = list(filter(lambda x: x != '\n', pages))
        links = list()
        pages.pop()
        for page in pages:
            image_link = page["data-srcset"]
            photo_name = image_link.split('.jpg')[0]
            if photo_name in list(map(lambda x: x.split('.jpg')[0], links)):
                continue
            if image_link != "":
                links.append(image_link)
        return links

    carousel = content[0].find_all('div', 'carousel-cell landscape')
    links = list()
    for page in carousel:
        image_link = page.next.next.next.next.next.next.next.next["data-srcset"]
        if image_link != "":
            links.append(image_link)
    return links


def get_post_text(post_html):
    content = post_html.find_all('div', 'post-body-content')
    if not content:
        return ""
    text = content[0].get_text()
    text = text.replace('Read Full Article', '')
    text = '\n'.join(list(filter(lambda x: x != '', text.split('\n'))))
    return text


def translate_text(text):
    print("Translating started")
    print("Text length:", len(text))
    translated = GoogleTranslator(source='en', target='ru').translate(text)
    print("Translating ended")
    return translated


def upload_photo(image_link):
    print("Uploading photo started")
    global session
    global group_id
    destination = session.photos.getWallUploadServer(group_id=group_id)
    image = requests.get(image_link, stream=True)
    # имя файла значения не имеет, но без него ВК не принимает фотографию
    data = ("sneaker.jpg", image.raw, image.headers['Content-Type'])
    meta = requests.post(destination['upload_url'],
                         files={'photo': data}).json()
    photo = session.photos.saveWallPhoto(group_id=group_id, **meta)[0]
    photo_id = 'photo' + str(photo['owner_id']) + '_' + str(photo['id'])
    print("Uploading photo ended")
    return photo_id


def create_post(text, photos_id, tracks_id):
    print("Creating post started")
    global session
    global group_id
    session.wall.post(owner_id=-group_id, message=text,
                      attachments=','.join(photos_id + tracks_id))
    print("Creating post ended")


def process_post(post_link):
    print("Posting post started")
    print(post_link)
    post_response = requests.get(post_link)
    post_html = BeautifulSoup(post_response.content, features="html.parser")
    text = get_post_text(post_html)
    if len(text) > 4000:
        print("Posting posts ended (text len exceeded 4000)", post_link)
        return
    elif len(text) == 0:
        print("NO TEXT SCRAPPED", post_link)
        return
    ru_text = translate_text(text)
    photo_links = get_images_links(post_html)
    if not photo_links:
        print("Posting post ended: NO PHOTOS SCRAPPED")
        return
    tracks_id = get_random_tracks_id(4)
    photos_id = [upload_photo(photo_link) for photo_link in photo_links]
    create_post(ru_text, photos_id, tracks_id)
    print("Posting post ended")


def parse_and_post():
    global hypebeast_link
    global latest_post_link
    footwear_response = requests.get(hypebeast_link)
    print("Posts parsing started")
    if footwear_response is None:
        print("No response")
        return
    footwear_html = BeautifulSoup(footwear_response.content, features="html.parser")
    sneakers_html_block = footwear_html.find_all('div', 'posts')
    print("Posts parsing ended")
    if not sneakers_html_block:
        print("Nothing to scrap")
        return
    posts_links = list()
    for i in range(len(sneakers_html_block)):
        post_blocks = sneakers_html_block[i].find_all('div', 'post-box')
        for block in post_blocks:
            posts_links.append(block["data-permalink"])

    links_reversed_order = []
    print("Processing posts started")
    for post_link in posts_links:
        if post_link == latest_post_link:
            break
        links_reversed_order.append(post_link)

    links_reversed_order.reverse()

    for post_link in tqdm(links_reversed_order):
        process_post(post_link)

    latest_post_link = posts_links[0]
    latest_post_link_file = open("/home/ubuntu/latest_post_link.txt", "w")
    latest_post_link_file.write(latest_post_link + '\n')
    latest_post_link_file.close()
    print("Processing posts ended")


while True:
    parse_and_post()
    minutes = randint(50, 70)
    print(f"Sleeping for {minutes} minutes\n>>>\n")
    sleep(minutes * 60)

