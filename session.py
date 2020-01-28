import time
from http import client

import requests

from utils import SoundCloudException

session = requests.Session()


def get_req(url, headers, params=None, tries=1, timeout=5):
    tries_count = 0
    success = False
    while success is False:
        try:
            res = session.get(url=url, headers=headers, params=params)
            if res.ok or res.status_code in [502, 503]:
                success = True
                return res
            if not res.ok:
                if res.status_code == 403:
                    raise SoundCloudException('Error status code %s with url : %s' % (res.status_code, url))
        except (client.IncompleteRead, requests.ConnectionError) as e:
            tries_count += 1
            if tries_count >= tries:
                raise SoundCloudException(e)
            time.sleep(timeout)
    return
