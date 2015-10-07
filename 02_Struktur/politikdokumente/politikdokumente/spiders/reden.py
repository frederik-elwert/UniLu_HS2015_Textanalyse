# -*- coding: utf-8 -*-
import re
from urlparse import urljoin
from datetime import datetime
# In order to parse German date like “18. September 2014”, German language support
# is activated.
import locale
locale.setlocale(locale.LC_ALL, 'de_DE.UTF-8')
ENC = locale.getpreferredencoding()

from lxml import html

import scrapy
from scrapy.utils.response import get_base_url
from scrapy.contrib.loader import ItemLoader
from scrapy.contrib.loader.processor import TakeFirst, Join

from politikdokumente.items import Rede

def extract_text(iterator):
    for element in iterator:
        yield html.fragment_fromstring(element).text_content()


class RedenSpider(scrapy.Spider):
    name = "reden"
    allowed_domains = ["bundesregierung.de"]
    start_urls = (
        'http://www.bundesregierung.de/SiteGlobals/Forms/Webs/Breg/Suche/DE/Suche_Solr_Formular.html?sortOrder=dateOfIssue_dt+desc%2C+score+desc&path=%2Fbpainternet%2Fcontent%2Fde%2Frede*+%2Fbpainternet%2Fcontentarchiv%2Fde%2Farchiv17%2Frede*&doctype=speech&resultsPerPage=50&searchtype=news',
    )

    def parse(self, response):
        '''Parse search result pages.'''
        # First, look for result pages and parse their content.
        for url in response.css('#searchResults h3 a::attr(href)').extract():
            url = urljoin(get_base_url(response), url)
            yield scrapy.Request(url, callback=self.parse_content)
        # Then, go to the next search result page.
        next_links = response.css('.forward a::attr(href)').extract()
        if next_links:
            next_link = next_links[0]
            url = urljoin(get_base_url(response), next_link)
            yield scrapy.Request(url, callback=self.parse)

    def parse_content(self, response):
        '''Parse content pages.'''
        loader = ItemLoader(item=Rede(), response=response)
        # Usually, we are only interested in the first item, e.g. for title, place, etc.
        loader.default_output_processor = TakeFirst()
        # Add fields
        loader.add_value('link', response.url)
        loader.add_css('title', '.text h1', extract_text)
        # Test if text has an abstract
        abstract = response.css('.abstract')
        if abstract:
            loader.add_css('abstract', '.abstract', extract_text)
            loader.add_css('text', '.abstract ~ p:not(.picture)',
                           extract_text, Join('\n'))
        else:
            loader.add_css('text', '.text p:not(.picture)',
                           extract_text, Join('\n'))
        # Metadata are in dt/dd pairs.
        keys = response.css('dl dt::text').extract()
        values = response.css('dl dd::text').extract()
        for key, value in zip(keys, values):
            if key == 'Datum:':
                match = re.search(r'(\d{1,2}\.\d{1,2}\.\d{2,4})', value)
                if match:
                    # '22.03.2011' format
                    value = match.group(1)
                    dt = datetime.strptime(value.encode(ENC), '%d.%m.%Y')
                else:
                    # '22. März 2011' format
                    dt = datetime.strptime(value.encode(ENC), '%d. %B %Y')
                loader.add_value('date', dt.date())
            elif key == 'Ort:':
                loader.add_value('place', value)
        return loader.load_item()