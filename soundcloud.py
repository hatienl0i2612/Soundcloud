import argparse
import io

from color import *
from download_http import Downloader
from progress_bar import ProgressBar
from session import get_req
from utils import *


class ExtractSoundCloud(ProgressBar):
    def __init__(self, *args, **kwargs):
        self._url = kwargs.get('url')
        self._file_save = kwargs.get('file_save')
        self._show_all_info = kwargs.get('show_all_info')
        self._headers = HEADERS
        self._API_BASE = 'https://api.soundcloud.com/'
        self._API_V2_BASE = 'https://api-v2.soundcloud.com/'
        self._BASE_URL = 'https://soundcloud.com/'
        self._IMAGE_REPL_RE = r'-([0-9a-z]+)\.jpg'
        self._cliend_id = ''

    def run(self):
        return self._real_extract()

    def _real_extract(self):
        string_regex_track = r'''(?x)^(?:https?://)?
                    (?:(?:(?:www\.|m\.)?soundcloud\.com/
                            (?!stations/track)
                            (?P<uploader>[\w\d-]+)/
                            (?!(?:tracks|albums|sets(?:/.+?)?|reposts|likes|spotlight)/?(?:$|[?#]))
                            (?P<title>[\w\d-]+)/?
                            (?P<token>[^?]+?)?(?:[?].*)?$)
                       |(?:api(?:-v2)?\.soundcloud\.com/tracks/(?P<track_id>\d+)
                          (?:/?\?secret_token=(?P<secret_token>[^&]+))?)
                    )
                    '''
        string_regex_track_sets = r'https?://(?:(?:www|m)\.)?soundcloud\.com/(?P<uploader>[\w\d-]+)/sets/(?P<title>[\w\d-]+)(?:/(?P<token>[^?/]+))?'

        sys.stdout.write(fg + '[' + fc + '*' + fg + '] : Extracting client id\n')
        self._cliend_id = Cache(site='soundcloud', text=self._cliend_id, key='client_id', type='json').load()
        if not self._cliend_id:
            self._cliend_id = self._find_client_id()
            Cache(site='soundcloud', text=self._cliend_id, key='client_id', type='json').store()

        regex_url = re.match(string_regex_track, self._url)
        regex_url_sets = re.match(string_regex_track_sets, self._url)

        query = {}
        if regex_url:
            track_id = regex_url.group('track_id')
            if track_id:
                token = regex_url.group('secret_token')
                if token:
                    query['secret_token'] = token

        if regex_url:
            dict_info_track = self._extract_info_dict(url_info=self._API_V2_BASE + 'resolve?url=' + self._url,
                                                      client_id=self._cliend_id, query=query)
            return self._download_track(dict_info_track=dict_info_track, _show_all_info=self._show_all_info)
        elif regex_url_sets:
            return self._extract_info_dict_for_sets(query=query,
                                                    url_info=self._API_V2_BASE + 'resolve?url=' + self._url,
                                                    client_id=self._cliend_id)

    def _find_client_id(self):
        res = get_req(url='https://soundcloud.com/', headers=self._headers)
        for src in reversed(re.findall(r'<script[^>]+src="([^"]+)"', res.text)):
            res_js_script = get_req(url=src, headers=self._headers)
            if res_js_script:
                cliend_id = re.findall(r'client_id\s*:\s*"([0-9a-zA-Z]{32})"', res_js_script.text)
                if cliend_id:
                    return cliend_id[0]
        raise SoundCloudException('Unable to extract client id')

    def _extract_info_dict_for_sets(self, *args, **kwargs):
        query = kwargs.get('query', {}).copy()
        query['client_id'] = kwargs.get('client_id')
        url_info = kwargs.get('url_info')
        response = get_req(url=url_info, headers=self._headers, params=query)
        res_json = response.json()

        _title = res_json.get('title')
        _id = res_json.get('id')
        _tracks = res_json.get('tracks')
        sys.stdout.write(fg + '[' + fc + '*' + fg + '] : Playlist %s found %s track.\n' % (_title, len(_tracks)))
        if _tracks:
            for ele, track in enumerate(_tracks):
                _id_track = track.get('id')
                dict_info_track = self._extract_info_dict(query=query,
                                                          url_info=self._API_V2_BASE + 'resolve?url=' + self._API_BASE + 'tracks/' + str(
                                                              _id_track),
                                                          client_id=self._cliend_id, ele=ele + 1)
                self._download_track(dict_info_track=dict_info_track, _show_all_info=self._show_all_info, ele=ele + 1)

    def _extract_info_dict(self, *args, **kwargs):
        ele = kwargs.get('ele') or ''
        text = fg + '\r[' + fc + '*' + fg + '] : Extracting info of track %s ... ' % (ele)
        spinner(text=text)
        query = kwargs.get('query', {}).copy()
        query['client_id'] = kwargs.get('client_id')
        url_info = kwargs.get('url_info')
        response = get_req(url=url_info, headers=self._headers, params=query)
        res_json = response.json()
        format_urls = set()
        formats = []

        _description = res_json.get('description')
        _title = res_json.get('title')
        _artwork_url = res_json.get('artwork_url')
        _id = res_json.get('id')

        formats.append({
            'title': _title,
            'id': _id,
            'artwork_url': _artwork_url,
            'description': _description,
        })

        def invalid_url(url):
            return not url or url in format_urls or re.search(r'/(?:preview|playlist)/0/30/', url)

        def add_format(f, protocol):
            mobj = re.search(r'\.(?P<abr>\d+)\.(?P<ext>[0-9a-z]{3,4})(?=[/?])', stream_url)
            if mobj:
                for k, v in mobj.groupdict().items():
                    if not f.get(k):
                        f[k] = v
            format_id_list = []
            if protocol:
                format_id_list.append(protocol)
            for k in ('ext', 'abr'):
                v = f.get(k)
                if v:
                    format_id_list.append(v)
            abr = f.get('abr')
            if abr:
                f['abr'] = int(abr)
            f.update({
                'format_id': '_'.join(format_id_list),
                'protocol': 'm3u8_native' if protocol == 'hls' else 'http',
            })
            formats.append(f)

        transcodings = try_get(
            res_json, lambda x: x['media']['transcodings'], list) or []
        for trans in transcodings:
            if not isinstance(trans, dict):
                continue
            format_url = trans.get('url')
            stream = self._extract_url_transcodings(format_url, query)
            if not isinstance(stream, dict):
                continue
            stream_url = stream.get('url')
            spinner(text=text)
            if invalid_url(stream_url):
                continue
            format_urls.add(stream_url)
            stream_format = trans.get('format') or {}
            protocol = stream_format.get('protocol')
            if protocol != 'hls' and '/hls' in format_url:
                protocol = 'hls'
            ext = None
            preset = trans.get('preset')
            if preset:
                ext = preset.split('_')[0]
            if ext not in KNOWN_EXTENSIONS:
                ext = mimetype2ext(stream_format.get('mime_type'))
            add_format({
                'url': stream_url,
                'ext': ext,
            }, 'http' if protocol == 'progressive' else protocol)
        sys.stdout.write(fg + '\r[' + fc + '*' + fg + '] : Extracting info of track %s. (done)\n' % (ele))
        return formats

    def _download_track(self, *args, **kwargs):
        _show_all_info = kwargs.get('_show_all_info') or False
        dict_info_track = kwargs.get('dict_info_track')
        title = sanitize_filename(s=dict_info_track[0].get('title'))
        n_show = get_name_show_cmd(ele=kwargs.get('ele'), title=title)
        path_save = '%s/%s' % (self._file_save, 'DOWNLOAD')
        if not os.path.exists(path=path_save):
            os.mkdir(path_save)
        sys.stdout.write(
            fg + '[' + fc + '*' + fg + '] : Starting download track %s.\n' % (n_show))
        if self._show_all_info is True:
            des = dict_info_track[0]
            io_file = '%s/%s.txt' % (path_save, title)
            with io.open(io_file, 'w', encoding='utf-8') as f:
                for k, v in des.items():
                    f.writelines('%s  :  %s\n\n' % (k, v))
            sys.stdout.write(
                fg + '[' + fc + '*' + fg + '] : %s.\n\n' % (io_file))
        else:
            protocol_m3u8_hls_mp3_128 = ''
            protocol_m3u8_hls_opus_64 = ''
            protocol_http_mp3_128 = ''
            for i in dict_info_track[1:]:
                protocol = i.get('protocol')
                if 'm3u8' in protocol:
                    format_id = i.get('format_id')
                    if 'mp3' in format_id:
                        protocol_m3u8_hls_mp3_128 = i.get('url')
                    elif 'opus' in format_id:
                        protocol_m3u8_hls_opus_64 = i.get('url')
                elif 'http' in protocol:
                    protocol_http_mp3_128 = i.get('url')

            if protocol_http_mp3_128:
                try:
                    down = Downloader(url=protocol_http_mp3_128)
                    down.download(filepath='%s/%s.mp3' % (path_save, title), callback=self.show_progress)
                    print('\n')
                except KeyboardInterrupt:
                    sys.stdout.write(
                        fc + sd + "\n[" + fr + sb + "-" + fc + sd + "] : " + fr + sd + "User Interrupted..\n")
                    sys.exit(0)
            elif protocol_m3u8_hls_mp3_128:
                print('use ffmpeg to download {}'.format(protocol_m3u8_hls_mp3_128))

    def _extract_url_transcodings(self, url_trans, query):
        res = get_req(url=url_trans, params=query, headers=self._headers)
        return res.json()


class ExtractSoundCloudPlaylist(ExtractSoundCloud):
    def __init__(self, *args, **kwargs):
        super(ExtractSoundCloudPlaylist, self).__init__(*args, **kwargs)
        self._BASE_URL_MAP = {
            'all': 'stream/users/%s',
            'tracks': 'users/%s/tracks',
            'albums': 'users/%s/albums',
            'sets': 'users/%s/playlists',
            'reposts': 'stream/users/%s/reposts',
            'likes': 'users/%s/likes',
            'spotlight': 'users/%s/spotlight',
        }

    def run(self):
        return self._real_extract()

    def _real_extract(self):
        string_regex = r'''(?x)
                                https?://
                                    (?:(?:www|m)\.)?soundcloud\.com/
                                    (?P<user>[^/]+)
                                    (?:/
                                        (?P<rsrc>tracks|albums|sets|reposts|likes|spotlight)
                                    )?
                                    /?(?:[?#].*)?$
                            '''
        mobj = re.match(string_regex, self._url)
        uploader = mobj.group('user')
        resource = mobj.group('rsrc') or 'all'
        url_info_user = self._API_V2_BASE + 'resolve?url=' + self._BASE_URL + uploader
        sys.stdout.write(fg + '[' + fc + '*' + fg + '] : Extracting client id\n')
        query = {}
        self._cliend_id = Cache(site='soundcloud', text=self._cliend_id, key='client_id', type='json').load()
        if not self._cliend_id:
            self._cliend_id = self._find_client_id()
            Cache(site='soundcloud', text=self._cliend_id, key='client_id', type='json').store()
        user = self._get_info_user(url=url_info_user, query=query)
        id_user = ''
        self.username = ''
        try:
            id_user = user.get('id')
            self.username = user.get('username')
            sys.stdout.write(
                fg + '[' + fc + '*' + fg + '] : Downloading playlist : %s (%s).\n' % (self.username, resource))
        except (AttributeError, KeyError, TypeError, IndexError):
            raise SoundCloudException('error cant get user_id, username,....')

        info_playlist = self._extract_playlist(url=self._API_V2_BASE + self._BASE_URL_MAP[resource] % id_user,
                                               query=query)
        tracks = info_playlist.get('collection')
        sys.stdout.write(fg + '[' + fc + '*' + fg + '] : Playlist %s found %s track.\n' % (self.username, len(tracks)))
        for ele, value in enumerate(tracks):
            _type = value.get('type')
            if 'track' in _type:
                track = value.get('track')
                permalink_url = track.get('permalink_url')
                dict_info_track = self._extract_info_dict(query=query,
                                                          url_info=self._API_V2_BASE + 'resolve?url=' + permalink_url,
                                                          client_id=self._cliend_id, ele=ele + 1)
                self._download_track(dict_info_track=dict_info_track, _show_all_info=self._show_all_info, ele=ele + 1)
            elif 'playlist' in _type:
                playlist_set = value.get('playlist')
                permalink_url = playlist_set.get('permalink_url')
                self._extract_info_dict_for_sets(query=query,
                                                 url_info=self._API_V2_BASE + 'resolve?url=' + permalink_url,
                                                 client_id=self._cliend_id)

    def _extract_playlist(self, url, query):
        query['client_id'] = self._cliend_id
        query.update({
            'limit': 2000000000,
            'linked_partitioning': '1',
        })
        res = get_req(url=url, headers=self._headers, params=query)
        if not isinstance(res.json(), dict):
            return
        return res.json()

    def _get_info_user(self, url, query):
        query['client_id'] = self._cliend_id
        res = get_req(url=url, headers=self._headers, params=query)
        if not isinstance(res.json(), dict):
            return
        return res.json()


class Cache():
    def __init__(self, site, text, key, type):
        self._site = site
        self._text = text
        self._key = key
        self._type = type

    def _get_root_path(self):
        env = os.getenv('XDG_CACHE_HOME', '~/.cache')
        res = os.path.join(env, 'abc-cache')
        return os.path.expandvars(os.path.expanduser(res))

    def _get_cache_path(self):
        return os.path.join(self._get_root_path(), self._site)

    def store(self):
        path_store = self._get_cache_path()
        if not os.path.exists(path_store):
            os.makedirs(path_store)
        with io.open('{}/{}.{}'.format(path_store, self._key, self._type), 'w', encoding='utf-8') as f:
            f.write(self._text)

    def load(self):
        path_store = self._get_cache_path()
        if path_store:
            try:
                try:
                    with io.open('{}/{}.{}'.format(path_store, self._key, self._type), 'r',
                                 encoding='utf-8') as cache_file:
                        return cache_file.read()
                except ValueError:
                    return None
            except IOError:
                pass  # No cache available
        else:
            return None


def main(argv):
    parser = argparse.ArgumentParser(description='Soundcloud - A tool for download track Soundcloud.')
    parser.add_argument('-u', '--url', type=str, help='Download url.', dest='url')
    parser.add_argument('-s', '--saved', type=str, default=os.getcwd(), help='Saved file name.', dest='file_name')
    parser.add_argument('-i', '--info', default=False, action='store_true', help='Show all info of track.',
                        dest='show_all_info')
    parser.add_argument('-l', '--playlist', type=str, help='Download playlist of user.', dest='play_list')
    args = parser.parse_args()
    if args.url:
        extract = ExtractSoundCloud(url=args.url, file_save=args.file_name,
                                    show_all_info=args.show_all_info)
        extract.run()
    elif args.play_list:
        extract = ExtractSoundCloudPlaylist(url=args.play_list, file_save=args.file_name,
                                            show_all_info=args.show_all_info)
        extract.run()


if __name__ == '__main__':
    try:
        if sys.stdin.isatty():
            main(sys.argv)
        else:
            argv = sys.stdin.read().split(' ')
            main(argv)
    except KeyboardInterrupt:
        sys.stdout.write(
            fc + sd + "\n[" + fr + sb + "-" + fc + sd + "] : " + fr + sd + "User Interrupted..\n")
        sys.exit(0)
