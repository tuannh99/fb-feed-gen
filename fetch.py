# -*- coding: utf-8 -*-
from bs4 import BeautifulSoup
from bs4 import SoupStrainer
from datetime import datetime
from dateutil.parser import *
import requests
import urlparse
import re
import urllib
import bleach


# allows us to get mobile version
user_agent_mobile = 'Mozilla/5.0 (Linux; U; Android 4.0.3; ko-kr; LG-L160L Build/IML74K) AppleWebkit/534.30 (KHTML, like Gecko) Version/4.0 Mobile Safari/534.30'
user_agent_desktop = 'Mozilla/5.0 (Windows NT 6.3; rv:36.0) Gecko/20100101 Firefox/36.0'

base_url = 'https://mbasic.facebook.com/'


def get_remote_data(url, ismobile=True, referer=None):
    ''' fetch website data as mobile or desktop browser'''
    user_agent = user_agent_mobile if ismobile else user_agent_desktop

    headers = {'User-Agent': user_agent}
    if referer:
        headers['Referer'] = referer

    r = requests.get(url, headers=headers)
    return r.content


def is_valid_username(username):
    ''' validate username '''

    expr = '^(?:pages\/)?(?P<display>[\w\-\.]{3,50})(\/\d{3,50})?$'
    result = re.match(expr, username)
    display = result.group('display') if result else None
    return (result, display)


def strip_invalid_html(content):
    ''' strips invalid tags/attributes '''

    allowed_tags = ['a', 'abbr', 'acronym', 'address', 'b', 'br', 'div', 'dl', 'dt',
                    'em', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'hr', 'i', 'img',
                    'li', 'ol', 'p', 'pre', 'q', 's', 'small', 'strike', 'strong',
                    'span', 'sub', 'sup', 'table', 'tbody', 'td', 'tfoot', 'th',
                    'thead', 'tr', 'tt', 'u', 'ul']
    allowed_attrs = {
        'a': ['href', 'target', 'title'],
        'img': ['src', 'alt', 'width', 'height'],
    }

    return bleach.clean(content,
                        tags=allowed_tags,
                        attributes=allowed_attrs,
                        strip=True)


def sub_video_link(m):
    expr = '\&amp\;source.+$'
    orig = m.group(1)
    unquoted = urllib.unquote(orig)
    new = re.sub(expr, '\" target', unquoted)
    return new


def fix_video_redirect_link(content):
    ''' replace video redirects with direct link '''

    expr = '\/video_redirect\/\?src=(.+)\"\starget'
    result = re.sub(expr, sub_video_link, content)
    return result


def sub_leaving_link(m):
    expr = '\&amp\;h.+$'
    orig = m.group(1)
    unquoted = urllib.unquote(orig)
    new = re.sub(expr, '\" target', unquoted)
    return new


def fix_leaving_link(content):
    ''' replace leaving fb links with direct link '''

    expr = 'http.+facebook\.com\/l.php\?u\=(.+)\"\starget'
    result = re.sub(expr, sub_leaving_link, content)
    return result


def fix_article_links(content):
    # fix video links
    v_fix = fix_video_redirect_link(content)
    # fix leaving links
    l_fix = fix_leaving_link(v_fix)
    # convert links to absolute
    a_fix = l_fix.replace('href="/', 'href="{0}'.format(base_url))

    return a_fix


def fix_guid_url(url):
    ''' add base + strip extra parameters '''

    expr = '([&\?]?(?:type|refid|source)=\d+&?.+$)'
    stripped = re.sub(expr, '', url)

    guid = urlparse.urljoin(base_url, stripped)
    return guid


def build_site_url(username):
    return urlparse.urljoin(base_url, username)


def build_article(byline, extra):
    ''' fix up article content '''

    content = byline.encode("utf8") + extra.encode("utf8")
    return strip_invalid_html(fix_article_links(content.decode("utf8")))


def extract_items(contents):
    ''' extract posts from page '''

    print 'Extracting posts from page'

    main_content = SoupStrainer('div', {'id': 'recent'})
    soup = BeautifulSoup(contents, "html.parser", parse_only=main_content)
    items = []

    if soup.div:
        for item in soup.div.div.div.children:
            item_link = item.find('a', text='Toàn bộ tin')
            if not item_link:
                continue  # ignore if no permalink found

            url = fix_guid_url(item_link['href'])
            date = parse(item.find('abbr').text.strip(), fuzzy=True, dayfirst=True)
            author = item.div.find('h3').a.get_text(strip=True)
            article_byline = item.div.div.contents[0]

            article_text = item.div.div.get_text(strip=True)
            if not article_text:
                article_text = item.div.find('h3').get_text()

            # add photos/videos
            article_extra = ''
            if item.div.div.next_sibling:
                article_extra = item.div.div.next_sibling.contents[0]

            # cleanup article
            article = build_article(article_byline, article_extra)

            items.append({
                'url': url,
                'title': article_text[:125],
                'article': article,
                'date': date,
                'author': author
            })

        print '{0} posts found'.format(len(items))

        return items
    # else
    return None
