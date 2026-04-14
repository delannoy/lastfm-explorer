#!/usr/bin/env python3

from __future__ import annotations
import enum
import json
import logging
import os
import time
import typing
import urllib.error
import urllib.parse
import urllib.request

import rich.logging

'''[MusicBrainz API](https://musicbrainz.org/doc/MusicBrainz_API/)'''

# to do:
#   define enum.Enum from functional api? `NonCoreEntities = StrEnum('NonCoreEntities', {_.upper().replace('-', '_'): _ for _ in ('collection', 'rating', 'tag')})`
#   implement lru_cache?

JSON_TYPE = typing.Dict[str, typing.Any]
VERSION = 2
USER_AGENT = f'delannoy/0.2 (a@delannoy.cc)' # https://musicbrainz.org/doc/MusicBrainz_API/Rate_Limiting#Provide_meaningful_User-Agent_strings
SLEEP = 1.01 # https://musicbrainz.org/doc/MusicBrainz_API/Rate_Limiting#Source_IP_address

logging.basicConfig(format='%(message)s', handlers=[rich.logging.RichHandler(rich_tracebacks=True, log_time_format="[%Y-%m-%d %H:%M:%S]")])
log = logging.getLogger(__name__)
log.setLevel(level=logging.DEBUG)


class NameSpace:
    @classmethod
    def get(cls, attribute: str):
        return getattr(cls, attribute)


class StrEnum(str, enum.Enum):
    @classmethod
    def list(cls):
        return sorted(enum.value for enum in cls)


class Request:

    @staticmethod
    def auth() -> urllib.request.OpenerDirector:
        '''Digest access authentication.'''
        # [HTTP Authentication in Python](https://stackoverflow.com/questions/720867/http-authentication-in-python)
        username, password = os.getenv('MUSICBRAINZ_USERNAME'), os.getenv('MUSICBRAINZ_PASSWORD')
        if not (username and password):
            raise ValueError('Please define your musicbrainz username and password as environment variables:\nexport MUSICBRAINZ_USERNAME=your_musicbrainz_username\nexport MUSICBRAINZ_PASSWORD=your_musicbrainz_password')
        password_manager = urllib.request.HTTPPasswordMgr()
        password_manager.add_password(realm='musicbrainz.org', uri='musicbrainz.org', user=username, passwd=password)
        return urllib.request.build_opener(urllib.request.HTTPDigestAuthHandler(passwd=password_manager))

    @classmethod
    def request(cls, endpoint: str, method: str = 'GET', data: JSON_TYPE|None = None, **params) -> urllib.request.Request:
        '''Instantiate a `urllib.request.Request` with url parameters given by `params` dictionary.'''
        logging.debug(f'sleeping {SLEEP} seconds...')
        time.sleep(SLEEP)
        url = f'https://musicbrainz.org/ws/{VERSION}/{endpoint}'
        headers = {'User-Agent': USER_AGENT, 'Accept': 'application/json'} #, 'Connection': 'Close'}
        params = {k: v for k, v in params.items() if (v is not None)}
        if 'user' in params.get('inc', ''):
            params.update({'client': USER_AGENT.split()[0]}) # https://musicbrainz.org/doc/MusicBrainz_API#Authentication
            urllib.request.install_opener(cls.auth())
        logging.debug(f'{endpoint} | {params}')
        return urllib.request.Request(method=method, url=f'{url}?{urllib.parse.urlencode(params)}', headers=headers, data=urllib.parse.urlencode(data or {}).encode('utf-8') or None)

    @staticmethod
    def response(request: urllib.request.Request) -> JSON_TYPE:
        '''Fetch response for `request` and handle exceptions.'''
        try:
            with urllib.request.urlopen(request) as response:
                logging.info(f'HTTP Request: {request.method} | {response.status} | {request.full_url}')
                return json.loads(response.read().decode('utf-8'))
        except urllib.error.HTTPError as http_error:
            logging.error(f'{http_error.status} | {http_error.reason} | {http_error.url}')
            if 'json' in http_error.headers.get('Content-Type', ''):
                logging.error(json.loads(http_error.read().decode('utf-8')).get('error'))
                raise http_error
        except urllib.error.URLError as url_error:
            logging.error(f'{url_error.reason}')
            raise url_error
        return {}

    @classmethod
    def get(cls, endpoint: str, **params) -> JSON_TYPE:
        '''Wrapper function for `urllib.request.urlopen` GET requests which accepts URL parameters from `params`.'''
        request = cls.request(endpoint=endpoint, **params)
        return cls.response(request=request)

    @classmethod
    def post(cls, endpoint: str, **params) -> JSON_TYPE:
        '''Wrapper function for `urllib.request.urlopen` POST requests which accepts URL parameters from `params` and `data` as the body.'''
        params.update(dict(client=USER_AGENT.split()[0]))
        headers = {'User-Agent': USER_AGENT, 'Content-Type': 'application/xml; charset=utf-8'}
        ...


def user_collections():
    mbid = 'f40041c8-462b-45ef-b115-e7da2971cb29'
    # editor = 'delannoy'
    url = f'https://musicbrainz.org/ws/2/collection/{mbid}/artists'
    # url = f'https://musicbrainz.org/ws/2/artist?collection={mbid}'
    password_manager = urllib.request.HTTPPasswordMgr()
    password_manager.add_password(realm='musicbrainz.org', uri='musicbrainz.org', user=os.getenv('MUSICBRAINZ_USERNAME'), passwd=os.getenv('MUSICBRAINZ_PASSWORD'))
    opener = urllib.request.build_opener(urllib.request.HTTPDigestAuthHandler(password_manager))
    headers = {'User-Agent': USER_AGENT, 'Accept': 'application/json'}
    request = urllib.request.Request(method='GET', url=url, headers=headers)
    return json.loads(opener.open(request).read().decode('utf-8'))



class CoreEntities(StrEnum):
    '''https://musicbrainz.org/doc/MusicBrainz_API#Introduction'''
    AREA = 'area'
    ARTIST = 'artist'
    EVENT = 'event'
    GENRE = 'genre'
    INSTRUMENT = 'instrument'
    LABEL = 'label'
    PLACE = 'place'
    RECORDING = 'recording'
    RELEASE = 'release'
    RELEASE_GROUP = 'release-group'
    SERIES = 'series'
    URL = 'url'
    WORK = 'work'


class NonCoreEntities(StrEnum):
    '''https://musicbrainz.org/doc/MusicBrainz_API#Introduction'''
    COLLECTION = 'collection'
    RATING = 'rating'
    TAG = 'tag'


class LookupIdentifiers(StrEnum):
    '''https://musicbrainz.org/doc/MusicBrainz_API#Introduction'''
    DISCID = 'discid'
    ISRC = 'isrc'
    ISWC = 'iswc'


class Release:

    class Format(StrEnum):
        '''https://musicbrainz.org/doc/Release/Format'''
        CD = 'cd'
        COPY_CONTROL_CD = 'copy control cd'
        DATA_CD = 'data cd'
        DTS_CD = 'dts cd'
        ENHANCED_CD = 'enhanced cd'
        HDCD = 'hdcd'
        CD_R = 'cd-r'
        CD_8CM = '8cm cd'
        BLU_SPEC_CD = 'blu-spec cd'
        SHM_CD = 'shm-cd'
        HQCD = 'hqcd'
        VINYL = 'vinyl'
        VINYL_7IN = '7" vinyl'
        VINYL_10IN = '10" vinyl'
        VINYL_12IN = '12" vinyl'
        FLEXI_DISC = 'flexi-disc'
        FLEXI_DISC_7IN = '7" flexi-disc'
        DIGITAL_MEDIA = 'digital media'
        CASSETTE = 'cassette'
        MICROCASSETTE = 'microcassette'
        DVD = 'dvd'
        DVD_AUDIO = 'dvd-audio'
        DVD_VIDEO = 'dvd-video'
        SACD = 'sacd'
        HYBRID_SACD = 'hybrid sacd'
        HYBRID_SACD_CD_LAYER = 'hybrid sacd (cd layer)'
        HYBRID_SACD_SACD_LAYER = 'hybrid sacd (sacd layer)'
        SHM_SACD = 'shm-sacd'
        DUALDISC = 'dualdisc'
        DUALDISC_CD_SIDE = 'dualdisc (cd side)'
        DUALDISC_DVD_VIDEO_SIDE = 'dualdisc (dvd-video side)'
        DUALDISC_DVD_AUDIO_SIDE = 'dualdisc (dvd-audio side)'
        MINIDISC = 'minidisc'
        BLU_RAY = 'blu-ray'
        BLU_RAY_R = 'blu-ray-r'
        HD_DVD = 'hd-dvd'
        VCD = 'vcd'
        SVCD = 'svcd'
        CDV = 'cdv'
        UMD = 'umd'
        SHELLAC = 'shellac'
        SHELLAC_7IN = '7" shellac'
        SHELLAC_10IN = '10" shellac'
        SHELLAC_12IN = '12" shellac'
        SD_CARD = 'sd card'
        SLOTMUSIC = 'slotmusic'
        OTHER = 'other'
        BETAMAX = 'betamax'
        CARTRIDGE = 'cartridge'
        HIPAC = 'hipac'
        PLAYTAPE = 'playtape'
        CED = 'ced'
        DAT = 'dat'
        DCC = 'dcc'
        DVDPLUS = 'dvdplus'
        DVDPLUS_CD_SIDE = 'dvdplus (cd side)'
        DVDPLUS_DVD_VIDEO_SIDE = 'dvdplus (dvd-video side)'
        DVDPLUS_DVD_AUDIO_SIDE = 'dvdplus (dvd-audio side)'
        EDISON_DIAMOND_DISC = 'edison diamond disc'
        FLOPPY_DISK = 'floppy disk'
        FLOPPY_DISK_3_5IN = '3.5" floppy disk'
        FLOPPY_DISK_5_25IN = '5.25" floppy disk'
        ZIP_DISK = 'zip disk'
        LASERDISC = 'laserdisc'
        LASERDISC_8IN = '8" laserdisc'
        LASERDISC_12IN = '12" laserdisc'
        MUSIC_CARD = 'music card'
        PATHE_DISC = 'pathé disc'
        PIANO_ROLL = 'piano roll'
        PLAYBUTTON = 'playbutton'
        REEL_TO_REEL = 'reel-to-reel'
        TEFIFON = 'tefifon'
        USB_FLASH_DRIVE = 'usb flash drive'
        VHD = 'vhd'
        VHS = 'vhs'
        VINYLDISC = 'vinyldisc'
        WAX_CYLINDER = 'wax cylinder'
        WIRE_RECORDING = 'wire recording'
        MULTITRACKS_RECORDING_4_TRACKS_8_TRACKS = '4 tracks/8 tracks/multitracks recording'
        ELCASET = 'elcaset'
        GRAMOPHONE_RECORD = 'gramophone record'

    class Status(StrEnum):
        '''https://musicbrainz.org/doc/Release#Status'''
        OFFICIAL = 'official'
        PROMOTION = 'promotion'
        BOOTLEG = 'bootleg'
        PSEUDO_RELEASE = 'pseudo-release'
        WITHDRAWN = 'withdrawn'
        CANCELLED = 'cancelled'

    class Type(StrEnum):
        '''https://musicbrainz.org/doc/Release_Group/Type'''
        ALBUM = 'album'
        BROADCAST = 'broadcast'
        EP = 'ep'
        OTHER = 'other'
        SINGLE = 'single'
        AUDIO_DRAMA = 'audio drama'
        AUDIOBOOK = 'audiobook'
        COMPILATION = 'compilation'
        DEMO = 'demo'
        DJ_MIX = 'dj-mix'
        FIELD_RECORDING = 'field recording'
        INTERVIEW = 'interview'
        LIVE = 'live'
        MIXTAPE_STREET = 'mixtape/street'
        REMIX = 'remix'
        SOUNDTRACK = 'soundtrack'
        SPOKENWORD = 'spokenword'



class Type:

    class Area(StrEnum):
        '''https://musicbrainz.org/doc/Area#Type'''
        COUNTRY = 'country'
        SUBDIVISION = 'subdivision'
        COUNTY = 'county'
        MUNICIPALITY = 'municipality'
        CITY = 'city'
        DISTRICT = 'district'
        ISLAND = 'island'

    class Artist(StrEnum):
        '''https://musicbrainz.org/doc/Artist#Type'''
        PERSON = 'person'
        GROUP = 'group'
        ORCHESTRA = 'orchestra'
        CHOIR = 'choir'
        CHARACTER = 'character'
        OTHER = 'other'

    class Event(StrEnum):
        '''https://musicbrainz.org/doc/Event#Type'''
        CONCERT = 'concert'
        FESTIVAL = 'festival'
        STAGE_PERFORMANCE = 'stage performance'
        AWARD_CEREMONY = 'award ceremony'
        LAUNCH_EVENT = 'launch event'
        CONVENTION_EXPO = 'convention/expo'
        MASTERCLASS_CLINIC = 'masterclass/clinic'

    class Instrument(StrEnum):
        '''https://musicbrainz.org/doc/Instrument#Type'''
        WIND_INSTRUMENT = 'wind instrument'
        STRING_INSTRUMENT = 'string instrument'
        PERCUSSION_INSTRUMENT = 'percussion instrument'
        ELECTRONIC_INSTRUMENT = 'electronic instrument'
        FAMILY = 'family'
        ENSEMBLE = 'ensemble'
        OTHER_INSTRUMENT = 'other instrument'

    class Label(StrEnum):
        '''https://musicbrainz.org/doc/Label/Type'''
        IMPRINT = 'imprint'
        ORIGINAL_PRODUCTION = 'original production'
        BOOTLEG_PRODUCTION = 'bootleg production'
        REISSUE_PRODUCTION = 'reissue production'
        DISTRIBUTOR = 'distributor'
        HOLDING = 'holding'
        RIGHTS_SOCIETY = 'rights society'

    class Place(StrEnum):
        '''https://musicbrainz.org/doc/Place#Type'''
        STUDIO = 'studio'
        VENUE = 'venue'
        STADIUM = 'stadium'
        INDOOR_ARENA = 'indoor arena'
        RELIGIOUS_BUILDING = 'religious building'
        EDUCATIONAL_INSTITUTION = 'educational institution'
        PRESSING_PLANT = 'pressing plant'
        OTHER = 'other'

    class Release:

        class Primary(StrEnum):
            '''https://musicbrainz.org/doc/Release_Group/Type#Primary_types'''
            ALBUM = 'album'
            SINGLE = 'single'
            EP = 'ep'
            BROADCAST = 'broadcast'
            OTHER = 'other'

        class Secondary(StrEnum):
            '''https://musicbrainz.org/doc/Release_Group/Type#Secondary_types'''
            COMPILATION = 'compilation'
            SOUNDTRACK = 'soundtrack'
            SPOKENWORD = 'spokenword'
            INTERVIEW = 'interview'
            AUDIOBOOK = 'audiobook'
            AUDIO_DRAMA = 'audio drama'
            LIVE = 'live'
            REMIX = 'remix'
            DJ_MIX = 'dj-mix'
            MIXTAPE_STREET = 'mixtape/street'
            DEMO = 'demo'
            FIELD_RECORDING = 'field recording'

    class Series(StrEnum):
        '''https://musicbrainz.org/doc/Series#Type'''
        RELEASE_GROUP_SERIES = 'release group series'
        RELEASE_SERIES = 'release series'
        RECORDING_SERIES = 'recording series'
        WORK_SERIES = 'work series'
        CATALOGUE = 'catalogue'
        ARTIST_SERIES = 'artist series'
        ARTIST_AWARD = 'artist award'
        EVENT_SERIES = 'event series'
        TOUR = 'tour'
        FESTIVAL = 'festival'
        RUN = 'run'
        RESIDENCY = 'residency'
