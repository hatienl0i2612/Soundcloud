import re
import subprocess
import sys
import time
from multiprocessing.dummy import Pool
from urllib.parse import urljoin

import requests
from Crypto.Cipher import AES
from requests import RequestException

from color import *
from progress_bar import ProgressBar


class ConnectionError(RequestException):
    """A Connection error occurred."""


early_py_version = sys.version_info[:2] < (2, 7)


class Download_m3u8(ProgressBar):
    def __init__(self, urlM3u8, name, callback=lambda *x: None, DirDownload=None, headers={}):
        self.urlM3u8 = urlM3u8
        self.session = requests.Session()
        self.DirDownload = DirDownload
        self.name = name
        self.lst_ts = []
        self.url_key = ''
        self.headers = headers
        self.count = 1
        self.d_ts = float()
        self.callback = callback
        self.ver = 'hls'

    def GetTsFromM3u8(self):
        r = self.session.get(self.urlM3u8, headers=self.headers)
        self.url_key = re.findall(r'URI=\"(.*?)\"', str(r.text))
        if self.url_key:
            self.url_key = self.url_key[0]
        self.lst_ts = re.findall(r'#EXTINF:(.*?),\n([\w\d$-_.+!*\'\(\),]+)\n', str(r.text))
        l = list(map(float, [i[0] for i in self.lst_ts]))
        self.sum_duration = sum(l)
        for index, [duration_ts, ts] in enumerate(self.lst_ts):
            if '.ts' in str(ts):
                self.lst_ts[index] = [duration_ts, urljoin(self.urlM3u8, ts)]

    def DownloadTsAndKey(self):
        if self.url_key:
            r = self.session.get(self.url_key, headers=self.headers)
            self.key = r.content
        self.l = len(self.lst_ts)
        thread = int(self.l ** (1 / 4))
        p = Pool(thread)
        dataout = p.map(self.Decript, self.lst_ts)
        p.close()
        name = '{}\{}'.format(self.DirDownload, self.name)
        with open(name, 'wb') as f:
            for data in dataout:
                f.write(data)
        dataout = b''
        cmd = '''ffmpeg -i "{}" -c copy "{}.mp4" -y'''.format(name, name)
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True)
        for line in process.stdout:
            pass
        if os.path.exists(name):
            if os.path.isfile(name):
                os.remove(name)

    def get_info_for_progress_bar(self, end, first, is_malformed, time_run=float()):
        if time_run:
            try:
                rate = ((float(end) - float(first)) / 1024.0) / time_run
                eta = (self.sum_duration - self.d_ts) / (rate * 1024.0)
            except ZeroDivisionError:
                is_malformed = True
                retVal = {"status": False,
                          "msg": "ZeroDivisionError : it seems, file has malfunction or is zero byte(s) .."}
                sys.stdout.write(fg + '[' + fr + '-' + fg + '] : %s\n' % (retVal['msg']))
                return
        else:
            rate = 0
            eta = 0
        return rate, eta, is_malformed

    def Decript(self, item, IV=None):
        is_malformed = False
        duration_ts, ts = item
        o1 = time.time()
        r = self.session.get(url=ts, headers=self.headers)
        data = r.content
        offset = self.d_ts
        self.d_ts += float(duration_ts)
        elapsed = time.time() - o1

        rate, eta, is_malformed = self.get_info_for_progress_bar(end=self.d_ts, first=offset, time_run=elapsed,
                                                                 is_malformed=is_malformed)

        if self.url_key:
            if len(self.key) % 16:
                retVal = {"status": False,
                          "msg": "Reason : Can not decode .ts file."}
                sys.stdout.write(fg + '[' + fr + '-' + fg + '] : %s\n' % (retVal['msg']))
                return
            if IV is None:
                IV = data[0:16]
                data = data[16:]
            datalen = len(data)
            decryptor = AES.new(self.key, AES.MODE_CBC, IV)
            chucksize = 64 * 1024
            dataOut = b''
            i = 0
            while True:
                chunk = data[i:i + chucksize]
                i += len(chunk)
                if i >= datalen:
                    chunk = decryptor.decrypt(chunk)
                    dataOut += chunk
                    break
                else:
                    dataOut += decryptor.decrypt(chunk)
            if not is_malformed:
                progress_stats = (self.d_ts, self.d_ts * 1.0 / self.sum_duration, rate, eta,self.ver,self.d_ts)
                self.show_progress(self.sum_duration, *progress_stats)
            return dataOut
        else:
            if not is_malformed:
                progress_stats = (self.d_ts, self.d_ts * 1.0 / self.sum_duration, rate, eta, self.ver, self.d_ts)
                self.show_progress(self.sum_duration, *progress_stats)
            return r.content

