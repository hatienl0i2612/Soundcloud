from setup import *


class ExtractSoundCloud(ProgressBar):
    _regex_track = r'''(?x)^(?:https?://)?
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
    _regex_track_set = r'''(?x)https?://(?:(?:www|m)\.)?soundcloud\.com/(?P<uploader>[\w\d-]+)/sets/(?P<title>[\w\d-]+)(?:/(?P<token>[^?/]+))?'''

    def __init__(self, *args, **kwargs):
        self._url = kwargs.get('url')
        self._path_save = kwargs.get('file_save') or os.getcwd()
        self._show_json_info = kwargs.get('show_json_info')
        self._headers = HEADERS
        self._API_BASE = 'https://api.soundcloud.com/'
        self._API_V2_BASE = 'https://api-v2.soundcloud.com/'
        self._BASE_URL = 'https://soundcloud.com/'
        self._IMAGE_REPL_RE = r'-([0-9a-z]+)\.jpg'
        self._cliend_id = ''
        self._cliend_id = Cache(site='soundcloud', text=self._cliend_id, key='client_id', type='json').load()
        if not self._cliend_id:
            self._cliend_id = self._find_client_id()
            Cache(site='soundcloud', text=self._cliend_id, key='client_id', type='json').store()
        self.query = {
            "client_id": self._cliend_id
        }

    def run_track(self, url=None):
        if not url:
            url = self._url
        mobj = re.match(self._regex_track, url)
        title_url = mobj.group("title")
        data_info_track = get_req(
            url=self._API_V2_BASE + 'resolve?url=' + url,
            headers=self._headers,
            params=self.query,
            type="json",
            note="2612"
        )
        return self.StartDownload(data_info_track=data_info_track)

    def run_set_playlist(self, url=None):
        if not url:
            url = self._url
        mobj = re.match(self._regex_track_set, url)
        title_url = mobj.group("title")
        data_info_sets = get_req(
            url=self._API_V2_BASE + 'resolve?url=' + url,
            headers=self._headers,
            type='json',
            params=self.query,
            note="Playlist track sets %s" % title_url
        )
        tracks = data_info_sets.get("tracks")
        to_screen("%s found %s" % (title_url, len(tracks)))
        for idx, track in enumerate(tracks):
            track_id = track.get("id")
            data_info_track = get_req(
                url="%sresolve?url=%stracks/%s" % (self._API_V2_BASE, self._API_BASE, track_id),
                headers=self._headers,
                type='json',
                note="2612",
                params=self.query
            )
            self.StartDownload(data_info_track=data_info_track, index=idx + 1, l=len(tracks))

    def StartDownload(self, data_info_track, index=None, l=None):
        format_urls = set()
        formats = []

        title = data_info_track.get("title")
        title = removeCharacter_filename(title)
        if index and l:
            to_screen("Downloading track %s (%s / %s)" % (title, index, l))
        else:
            to_screen("Downloading track %s" % title)

        if self._show_json_info:
            sys.stdout.write(json.dumps(data_info_track,ensure_ascii=False))
            return

        DirDownload = os.path.join(self._path_save, "DOWNLOAD")
        if not os.path.exists(DirDownload):
            os.mkdir(DirDownload)
        output_video = os.path.join(DirDownload, "%s.mp3" % title)
        if os.path.exists(output_video):
            to_screen("Already downloaded")
            return

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

        def invalid_url(url):
            return not url or url in format_urls or re.search(r'/(?:preview|playlist)/0/30/', url)

        transcodings = try_get(
            data_info_track, lambda x: x['media']['transcodings'], list) or []
        for trans in transcodings:
            if not isinstance(trans, dict):
                continue
            format_url = trans.get('url')
            stream = self._extract_url_transcodings(format_url)
            if not isinstance(stream, dict):
                continue
            stream_url = stream.get('url')
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

        formats = sorted(formats, key=lambda x: (x["abr"], 1 if "http" in x["protocol"] else -1))
        will_down = formats[-1]

        if "http" in will_down.get("protocol"):
            down = Downloader(url=will_down.get("url"))
            down.download(filepath='%s/%s.mp3' % (DirDownload, title), callback=self.show_progress)
        elif "m3u8" in will_down.get("protocol"):
            use_ffmpeg(
                url=will_down.get("url"),
                filename=title,
                DirDownload=DirDownload,
                ext="mp3"
            )
        else:
            to_screen("Can not download %s, pls contact DEV to fix." % data_info_track.get("permalink_url"))
        return

    def _extract_url_transcodings(self, url_trans):
        return get_req(url=url_trans, params=self.query, headers=self._headers, type='json',
                       note="2612")

    def _find_client_id(self):
        res = get_req(url='https://soundcloud.com/', headers=self._headers, note="Downloading client id")
        for src in reversed(re.findall(r'<script[^>]+src="([^"]+)"', res.text)):
            res_js_script = get_req(url=src, headers=self._headers, note="Downloading js content.")
            if res_js_script:
                cliend_id = re.findall(r'client_id\s*:\s*"([0-9a-zA-Z]{32})"', res_js_script.text)
                if cliend_id:
                    return cliend_id[0]
        raise ErrorException('Unable to extract client id')


class ExtractSoundCloudPlaylist(ExtractSoundCloud):
    _regex_playlist = r'''(?x)
                                https?://
                                    (?:(?:www|m)\.)?soundcloud\.com/
                                    (?P<user>[^/]+)
                                    (?:/
                                        (?P<rsrc>tracks|albums|sets|reposts|likes|spotlight)
                                    )?
                                    /?(?:[?#].*)?$
                            '''

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

    def run_playlist(self, url=None):
        if not url:
            url = self._url
        mobj = re.match(self._regex_playlist, self._url)
        uploader = mobj.group('user')
        resource = mobj.group('rsrc') or 'all'
        data_info_user = get_req(
            url=self._API_V2_BASE + 'resolve?url=' + self._BASE_URL + uploader,
            headers=self._headers,
            type='json',
            params=self.query,
            note="Downloading info of user %s" % uploader,
        )
        user_id = data_info_user.get("id")
        username = data_info_user.get("username")
        if not user_id:
            raise ErrorException("Can not find user id.")
        data_playlist_track_user = get_req(
            url=self._API_V2_BASE + self._BASE_URL_MAP[resource] % user_id,
            headers=self._headers,
            type='json',
            params={
                'limit': 2000000000,
                'linked_partitioning': '1',
                "client_id": self._cliend_id
            },
            note="Downloading track of user %s" % username
        )
        tracks = data_playlist_track_user.get('collection')
        to_screen("Playlist %s found %s" % (username,len(tracks)))
        for idx,track in enumerate(tracks):
            _type = track.get("kind") or track.get("type")
            if "track" in _type:
                permalink_url = try_get(
                    track,lambda x:x["track"]["permalink_url"]
                ) or try_get(
                    track,lambda x:x["permalink_url"]
                )
                self.run_track(permalink_url)
            elif "playlist" in _type:
                permalink_url = try_get(
                    track, lambda x: x["playlist"]["permalink_url"]
                ) or try_get(
                    track, lambda x: x["permalink_url"]
                )
                self.run_set_playlist(permalink_url)

class Cache():
    def __init__(self, site, text, key, type):
        self._site = site
        self._text = text
        self._key = key
        self._type = type

    def _get_root_path(self):
        env = os.getenv('XDG_CACHE_HOME', '~/.cache')
        res = os.path.join(env, 'tm-cache')
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


class Base:
    def __init__(self, *args, **kwargs):
        tm = ExtractSoundCloudPlaylist(*args, **kwargs)
        url = kwargs.get("url")

        if re.match(tm._regex_track, url):
            tm.run_track()
        if re.match(tm._regex_track_set, url):
            tm.run_set_playlist()
        if re.match(tm._regex_playlist, url):
            tm.run_playlist()


def main(argv):
    parser = argparse.ArgumentParser(description='Soundcloud - A tool for download track Soundcloud.')
    parser.add_argument('url', type=str, help='Url.')

    opts = parser.add_argument_group("Options")
    opts.add_argument('-s', '--save', type=str, default=os.getcwd(), help='Path to save', dest='path_save', metavar='')
    opts.add_argument('-j', '--json', default=False, action='store_true', help="Show json of info media.",
                      dest='show_json_info')
    args = parser.parse_args()
    Base(
        url=args.url,
        path_save=args.path_save,
        show_json_info=args.show_json_info,
    )


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
