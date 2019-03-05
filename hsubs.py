from json import load
from collections import namedtuple
from database import list_all_shows, delete_data, get_show_id_by_name
import requests
import logging
import re

from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


class ScheduleGenerator:
    """
    Class that generates the schedule by scraping HS's schedule page.
    """

    def __init__(self):
        self.config = load(open('config.json', 'r'))
        self.days = self.config['en_gb']['day_array']
        self.show = namedtuple('Show', ['id', 'day', 'title', 'time', 'link'])
        self.schedulelink = 'https://horriblesubs.info/release-schedule/'
        self.baselink = 'https://horriblesubs.info'
        self.req = requests.get(self.schedulelink)
        self.tree = BeautifulSoup(self.req.text, 'lxml')
        self.id = 0

    def iter_schedule(self, days=None):
        if not days:
            days = self.days
        elif not isinstance(days, (list, tuple)):
            days = [days]

        tables = self.tree.select('#main > div > article > div > table')

        for day in days:
            # tables start from 1 rather than from 0, 1 day = 1 table
            dayindex = self.days.index(day)
            rows = tables[dayindex].find_all('tr', recursive=False)

            for item in rows:
                title = item.a.text
                time = item('td')[1].text
                link = f'{self.baselink}{item.a["href"]}'

                show_id = get_show_id_by_name(title)

                if show_id is None:
                    page = requests.get(link).text
                    show_id = re.search(r'var hs_showid = (\d+);', page).group(1)

                yield self.show(show_id, day, title, time, link)

    def update_schedule(self):
        self.req = requests.get(self.schedulelink)
        self.tree = BeautifulSoup(self.req.text, 'lxml')
        self.id += 1
        showlist = {show.title for show in self.iter_schedule()}
        all_shows = list_all_shows()
        if showlist == all_shows:
            logger.info(f"Update successful, id: {self.id}")
            return True
        else:
            logger.warning("Show mismatch found, flushing old data...")
            delete_data()
            return False

    @staticmethod
    def shorten_magnet(magnet_link):
        url = f'http://mgnet.me/api/create?m={magnet_link}'
        return requests.get(url).json()['shorturl']

    def pretty_print(self):
        for day in self.days:
            print(day)
            for item in self.iter_schedule(day):
                if item.day == day:
                    print(f'• {item.title} @ {item.time} PST')
            print('-----------------------------------------')


def check_show_up(show_title):
    url = 'https://horriblesubs.info/api.php?method=getlatest'
    page = requests.get(url)

    if show_title.replace('–', '-') in page.text:
        return True
    else:
        return False


def get_show_ep_magnet(show_title):
    show_id = get_show_id_by_name(show_title)

    url = f'https://horriblesubs.info/api.php?method=getshows&type=show&showid={show_id}'
    page = requests.get(url)
    soup = BeautifulSoup(page.text, 'lxml')

    episode = soup.select('a.rls-label > strong')[0].text
    magnets = soup.select('span.hs-magnet-link > a')
    magnet720 = magnets[1]['href']
    magnet1080 = magnets[2]['href']
    return episode, magnet720, magnet1080
