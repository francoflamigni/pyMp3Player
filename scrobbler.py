# -*- coding: utf-8 -*-
import logging
import re
import urllib.error
import urllib.parse
import urllib.request
import re
import struct
import lyricsgenius as genius
logger = logging.getLogger(__package__)

formatter = logging.Formatter(
    "[%(asctime)s] {%(pathname)s:%(lineno)d} %(levelname)s - %(message)s"
)

from utils import waitCursor

null_handler = logging.NullHandler()
null_handler.setFormatter(formatter)
logger.addHandler(null_handler)


# this is the function you should call with the url to get all data sorted as a object in the return
def get_server_info(url):
    if url.endswith(".pls") or url.endswith("listen.pls?sid=1"):
        address = check_pls(url)
    else:
        address = url
    if isinstance(address, str):
        meta_interval = get_all_data(address)
    else:
        meta_interval = {"status": 0, "metadata": None}

    return meta_interval


def get_all_data(address):
    status = 0

    request = urllib.request.Request(address)
    user_agent = "iTunes/9.1.1"
    request.add_header("User-Agent", user_agent)
    request.add_header("icy-metadata", 1)
    try:
        response = urllib.request.urlopen(request, timeout=6)
        headers = dict(response.info())

        if "Server" in headers:
            shoutcast = headers["Server"]
        elif "X-Powered-By" in headers:
            shoutcast = headers["X-Powered-By"]
        elif "icy-notice1" in headers:
            shoutcast = headers["icy-notice2"]
        else:
            shoutcast = True

        if isinstance(shoutcast, bool):
            if shoutcast:
                status = 1
            else:
                status = 0
            metadata = False
        elif "SHOUTcast" in shoutcast:
            status = 1
            metadata = shoutcast_check(response, headers, False)
        elif "Icecast" or "137" or "StreamMachine" in shoutcast:
            status = 1
            metadata = shoutcast_check(response, headers, True)
        elif shoutcast:
            status = 1
            metadata = shoutcast_check(response, headers, True)
        else:
            metadata = False
        response.close()
        return {"status": status, "metadata": metadata}

    except urllib.error.HTTPError as e:
        logger.exception("    Error, HTTPError = ")

        return {"status": status, "metadata": None}

    except urllib.error.URLError as e:
        logger.exception("    Error, URLError: ")
        return {"status": status, "metadata": None}

    except Exception as err:
        logger.exception("    Error: ")
        return {"status": status, "metadata": None}


def check_pls(address):
    try:
        stream = None
        response = urllib.request.urlopen(address, timeout=2)
        for line in response:
            if line.startswith(b"File1="):
                stream = line.decode()

        response.close()
        if stream:
            return stream[6:].strip("\n")
        else:
            return False
    except Exception:
        return False


def shoutcast_check(response, headers, is_old):
    bitrate = None
    contenttype = None

    if "icy-br" in headers:
        if is_old:
            bitrate = headers["icy-br"].split(",")[0]
        else:
            bitrate = headers["icy-br"]
            bitrate = bitrate.rstrip()

    if "icy-metaint" in headers:
        icy_metaint_header = headers["icy-metaint"]
    else:
        icy_metaint_header = None

    if "Content-Type" in headers:
        contenttype = headers["Content-Type"].rstrip()
    elif "content-type" in headers:
        contenttype = headers["content-type"].rstrip()

    if icy_metaint_header:
        metaint = int(icy_metaint_header)
        read_buffer = metaint + 255
        content = response.read(read_buffer)

        start = "StreamTitle='"
        end = "';"

        try:
            title = (
                re.search(bytes("%s(.*)%s" % (start, end), "utf-8"), content[metaint:])
                .group(1)
                .decode("utf-8")
            )
            a = (
                re.sub("StreamUrl='.*?';", "", title)
                .replace("';", "")
                .replace("StreamUrl='", "")
            )
            title = re.sub("&artist=.*", "", title)
            title = re.sub("http://.*", "", title)
            title.rstrip()
        except Exception as err:
            logger.exception("songtitle error: ")
            title = content[metaint:].split(b"'")[1]

        return {"song": title, "bitrate": bitrate, "contenttype": contenttype}
    else:
        logger.debug('No metaint')
        return False


def strip_tags(text):
    finished = 0
    while not finished:
        finished = 1
        start = text.find("<")
        if start >= 0:
            stop = text[start:].find(">")
            if stop >= 0:
                text = text[:start] + text[start + stop + 1 :]
                finished = 0
    return text

def get_thumbnail(url):
    if len(url) > 0:
        try:
            im = urllib.request.urlopen(url).read()
            return im
            with open("c:/temp/test.png", "wb") as f:
                f.write(im)
        except:
            pass
    return None

def get_title(url):
    title = ''
    request = urllib.request.Request(url, headers={'Icy-MetaData': 1})  # request metadata
    try:
        response = urllib.request.urlopen(request)
    except:
        return title

    metaint = int(response.headers['icy-metaint'])
    for _ in range(10):  # # title may be empty initially, try several times
        response.read(metaint)  # skip to metadata
        metadata_length = struct.unpack('B', response.read(1))[0] * 16  # length byte
        metadata = response.read(metadata_length).rstrip(b'\0')
        # extract title from the metadata
        m = re.search(br"StreamTitle='([^']*)';", metadata)
        if m:
            title = m.group(1)
            if title:
                break

    if isinstance(title, str) is False:
        encoding = 'latin1'  # default: iso-8859-1 for mp3 and utf-8 for ogg streams
        title = title.decode(encoding, errors='replace')
    return title

def song_text(artist, song):
    txt = ''
    api = genius.Genius('RAiSHWVhVPsbCpdYygn-I6g9CAHa5DwXvujb_Tv98U1K21JWSigV3YLc3w7miV1l', verbose=True, timeout=10,
                        remove_section_headers=True)
    waitCursor(True)
    try:
        #art = api.search_artist(artist, max_songs=0)
        song = api.search_song(song, artist, None, False)
        if song is not None:
            txt = song.lyrics
            aa = txt.find('\n')
            txt = txt[aa + 1:]
            a = 0
    except ConnectionError as err:
        a = 0
    waitCursor()
    return txt
