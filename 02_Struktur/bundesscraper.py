#!/usr/bin/env python3

import sys
import argparse
import logging
import re
import time
import datetime
import csv
from collections import namedtuple
# Required for parsing German dates
import locale
locale.setlocale(locale.LC_ALL, 'de_DE.UTF-8')

from lxml import html

START_URL = 'http://www.bundesregierung.de/SiteGlobals/Forms/Webs/Breg/Suche/DE/Nachrichten/Redensuche2_formular.html?nn=8988&searchtype.HASH=e5e7611fd92022248dd0&path.HASH=631e69fa04dc338f202c&path=%2Fbpainternet%2Fcontent%2Fde%2Frede*+%2Fbpainternet%2Fcontentarchiv%2Fde%2Farchiv17%2Frede*&doctype=speech&doctype.HASH=fb7e3f87bcd598d5d3d&searchtype=news'
PAUSE = 2

Page = namedtuple('Page', ['url', 'title', 'date', 'place', 'abstract', 'text'])

def crawl(start_url, outfile):
    logging.debug('Start crawling links.')
    links = find_links(start_url)
    logging.debug('Crawling links finished. Found {} links.'.format(len(links)))
    logging.debug('Start crawling pages.')
    pages = [scrape_page(link) for link in links]
    logging.debug('Crawling pages finished.')
    logging.debug('Writing output.')
    save(pages, outfile)
    logging.debug('Done.')


def find_links(start_url):
    links = []
    next_page = start_url
    while next_page:
        logging.debug('Crawling list page {}.'.format(next_page))
        new_links, next_page = scrape_list_page(next_page)
        logging.debug('Found {} links.'.format(len(new_links)))
        links.extend(new_links)
    return links

def scrape_list_page(url):
    time.sleep(PAUSE)
    # Get and parse page
    doc = html.parse(url)
    root = doc.getroot()
    root.make_links_absolute(url)
    # Extract links to details pages
    link_elements = root.cssselect('#searchResults h3 a')
    links = [element.get('href') for element in link_elements]
    # Extract link to next page
    next_link_elements = root.cssselect('.forward a')
    if next_link_elements:
        next_page = next_link_elements[0].get('href')
    else:
        next_page = None
    return (links, next_page)

def scrape_page(url):
    time.sleep(PAUSE)
    # Get and parse page
    doc = html.parse(url)
    root = doc.getroot()
    # Title
    title = root.cssselect('#main h1')[0].text_content()
    # Metadata fields: Date and place
    date = None
    place = None
    metadata = root.cssselect('#main dl')
    if metadata:
        metadata = metadata[0]
        keys = metadata.cssselect('dt')
        values = metadata.cssselect('dd')
        for key, value in zip(keys, values):
            if key.text_content().strip(':') == 'Datum':
                date = parse_date(value.text_content())
            elif key.text_content().strip(':') == 'Ort':
                place = value.text_content()
    # Abstract and text
    abstract = root.cssselect('#main .abstract')
    if abstract:
        abstract = abstract[0].text_content()
    else:
        abstract = None
    paragraphs = root.cssselect('#main .basepage_pages > p')
    paragraphs = [p.text_content() for p in paragraphs]
    text = '\n\n'.join(paragraphs)
    # Return
    if ';jsessionid' in url:
        url = url.split(';jsessionid')[0]
    page = Page(url=url,
                title=title,
                date=date,
                place=place,
                abstract=abstract,
                text=text)
    return page

def parse_date(date_string):
    date_string = date_string.strip()
    date_patterns = [
        (r'\d+\.\d+\.\d+', '%d.%m.%Y'),
        (r'\d+\. \w+ \d+', '%d. %B %Y')
    ]
    date = None
    for regex, pattern in date_patterns:
        match = re.match(regex, date_string)
        if match:
            # Limit date string to part that matches the regex.
            # Prevents parsing errors with additional data like " 17:00 Uhr"
            date_string = match.group(0)
            date = datetime.datetime.strptime(date_string, pattern).date()
    if date == None:
        logging.warn('Could not parse date "{}"'.format(date_string))
    return date

def save(pages, outfile):
    writer = csv.writer(outfile)
    writer.writerow(Page._fields)
    for page in pages:
        writer.writerow(page)

def main():
    # Parse commandline arguments
    arg_parser = argparse.ArgumentParser()
    arg_parser.add_argument('-v', '--verbose', action='store_true')
    arg_parser.add_argument('-o', '--outfile', default=sys.stdout,
                            type=argparse.FileType('w'))
    args = arg_parser.parse_args()
    # Set up logging
    if args.verbose:
        level = logging.DEBUG
    else:
        level = logging.ERROR
    logging.basicConfig(level=level)
    # Do work
    crawl(START_URL, args.outfile)
    #scrape_page('http://www.bundesregierung.de/Content/DE/Rede/2015/09/2015-09-28-rede-merkel-global-leaders.htm')
    # Return exit value
    return 0


if __name__ == '__main__':
    sys.exit(main())
