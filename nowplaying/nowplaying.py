#!/usr/bin/env python3

from __future__ import annotations
import functools
import http.server
import json
import logging
import os
import pathlib
import sys
import urllib.error
import urllib.parse
import urllib.request

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(message)s')

PORT = 3000

LATITUDE = float(os.environ.get('LOCATION_LATITUDE', 46.23424))
LONGITUDE = float(os.environ.get('LOCATION_LONGITUDE', 6.08025))

LASTFM_KEY = os.environ.get('LASTFM_KEY', '').replace('-', '')
LASTFM_USER = os.environ.get('LASTFM_USER', 'adelannoy')

if not LASTFM_KEY:
    logging.error('Error: LASTFM_KEY environment variable must be set (https://www.last.fm/api/account/create to create one or https://www.last.fm/api/accounts to view existing ones).')
    sys.exit(1)

def query(url: str) -> dict:
    '''Query and parse JSON with basic error handling.'''
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'NowPlaying/1.0'})
        with urllib.request.urlopen(req, timeout=5) as response:
            return json.loads(response.read().decode())
    except urllib.error.HTTPError as e:
        logging.error(f'HTTP {e.code} for {url}')
        return {'error': f'HTTP {e.code}'}
    except Exception as e:
        logging.error(f'Request failed for {url}: {e}')
        return {'error': 'Connection failed'}

def lastfm_nowplaying(user: str, api_key: str) -> dict[str, int|bool|str]:
    '''Query and parse the latest listen from LASTFM.'''
    url = f'https://ws.audioscrobbler.com/2.0/?method=user.getrecenttracks&user={user}&api_key={api_key}&format=json&limit=1'
    data = query(url=url)
    if 'error' in data:
        return data
    tracks = data.get('recenttracks', {}).get('track', [])
    if not tracks:
        return {'error': 'No tracks found'}
    total_listens = data.get('recenttracks', {}).get('@attr', {}).get('total', 0)
    track = tracks[0]
    images = track.get('image', [])
    artist_name, album_name, track_name = track.get('artist', {}).get('#text', ''), track.get('album', {}).get('#text', ''), track.get('name', '')
    stats = lastfm_track_stats(user, api_key, track_name, artist_name)
    return {
        'playing': (track.get('@attr', {}).get('nowplaying') == 'true'),
        'artist': artist_name,
        'album': album_name,
        'track': track_name,
        'image': images[-1].get('#text', '') if images else '',
        'total_listens': total_listens,
        'track_listens': stats['track_listens'],
        'loved': stats['loved'],
    }

def lastfm_track_stats(user: str, api_key: str, track_name: str, artist_name: str) -> dict[str, int|bool]:
    '''Fetches stats (playcount, loved) for a specific track from LASTFM.'''
    if not track_name or not artist_name:
        return {'track_listens': 0, 'loved': False}
    url = f'https://ws.audioscrobbler.com/2.0/?method=track.getInfo&api_key={api_key}&artist={urllib.parse.quote(artist_name)}&track={urllib.parse.quote(track_name)}&username={user}&format=json'
    data = query(url=url)
    if 'error' in data:
        return {'track_listens': 0, 'loved': False}
    track_info = data.get('track', {})
    return {
        'track_listens': int(track_info.get('userplaycount', 0)),
        'loved': int(track_info.get('userloved', 0)) == 1
    }

@functools.lru_cache(maxsize=1)
def resolve_location(latitude: float, longitude: float) -> str:
    '''Resolve coordinates to a city name.'''
    if not latitude or not longitude:
        return 'Unknown'
    url = f'https://nominatim.openstreetmap.org/reverse?lat={latitude}&lon={longitude}&format=json' # https://nominatim.org/release-docs/latest/api/Reverse/
    data = query(url=url)
    addr = data.get('address', {})
    return addr.get('city') or addr.get('town') or addr.get('village') or addr.get('county') or 'Unknown'

def weather_description(code: int) -> tuple[str, str]:
    '''https://open-meteo.com/en/docs#weather_variable_documentation'''
    codes = {
        0: ('Clear sky', '☀️'),
        1: ('Mainly clear', '🌤️'), 2: ('Partly cloudy', '⛅'), 3: ('Overcast', '☁️'),
        45: ('Fog', '🌫️'), 48: ('Depositing rime fog', '🌫️'),
        51: ('Light drizzle', '🌧️'), 53: ('Moderate drizzle', '🌧️'), 55: ('Dense drizzle', '🌧️'),
        56: ('Light freezing drizzle', '🌧️'), 57: ('Dense freezing drizzle', '🌧️'),
        61: ('Slight rain', '🌧️'), 63: ('Moderate rain', '🌧️'), 65: ('Heavy rain', '🌧️'),
        66: ('Light freezing rain', '🌧️'), 67: ('Heavy freezing rain', '🌧️'),
        71: ('Slight snow fall', '❄️'), 73: ('Moderate snow fall', '❄️'), 75: ('Heavy snow fall', '❄️'),
        77: ('Snow grains', '❄️'),
        80: ('Slight rain showers', '🌦️'), 81: ('Moderate rain showers', '🌦️'), 82: ('Violent rain showers', '🌦️'),
        85: ('Slight snow showers', '🌨️'), 86: ('Heavy snow showers', '🌨️'),
        95: ('Thunderstorm', '⛈️'),
        96: ('Thunderstorm, slight hail', '⛈️'), 99: ('Thunderstorm, heavy hail', '⛈️'),
    }
    return codes.get(code, ('Unknown', '🌡️'))

def weather(latitude: float, longitude: float) -> dict:
    '''https://open-meteo.com/en/docs#api_documentation'''
    if not latitude or not longitude:
        return {'error': 'Coordinates not set'}
    url = f'https://api.open-meteo.com/v1/forecast?latitude={latitude}&longitude={longitude}&current=temperature_2m,weather_code&daily=temperature_2m_max,temperature_2m_min,precipitation_probability_max&timezone=auto' # https://open-meteo.com/en/docs#daily_parameter_definition
    data = query(url=url)
    if 'error' in data:
        return data
    current = data.get('current', {})
    daily = data.get('daily', {})
    round_first_value = lambda var: round(float(daily[var][0])) if (daily.get(var, [None])[0] is not None) else '--'
    description, emoji = weather_description(code=current.get('weather_code', -1))
    return {
            'temperature': current.get('temperature_2m', '--'),
            'high': round_first_value('temperature_2m_max'),
            'low': round_first_value('temperature_2m_min'),
            'precipitation': round_first_value('precipitation_probability_max'),
            'description': description,
            'emoji': emoji,
            'location': resolve_location(LATITUDE, LONGITUDE),
            }


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/':
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            html_path = pathlib.Path(__file__).parent / 'index.html'
            self.wfile.write(html_path.read_bytes())
        elif self.path == '/api/nowplaying':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            result = lastfm_nowplaying(LASTFM_USER, LASTFM_KEY)
            self.wfile.write(json.dumps(result).encode('utf-8'))
        elif self.path == '/api/weather':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            result = weather(LATITUDE, LONGITUDE)
            self.wfile.write(json.dumps(result).encode('utf-8'))
        else:
            self.send_response(404)
            self.end_headers()
    def log_message(self, format, *args):
        pass


def run():
    server_address = ('', PORT)
    httpd = http.server.ThreadingHTTPServer(server_address, Handler)
    logging.info(f"Starting NowPlaying on http://localhost:{PORT}")
    logging.info(f"Tracking Last.fm user: {LASTFM_USER}")

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        logging.info("Shutting down server...")
        httpd.server_close()


if __name__ == '__main__':
    run()
