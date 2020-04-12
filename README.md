# ***Download Soundcloud***

***Soundcloud - A tool for download track of [`Soundcloud`](https://soundcloud.com/).***

[![Capture.png](https://i.postimg.cc/qqd8ZWGP/Capture.png)](https://postimg.cc/1nJn8C2B)

# ***Usage***

```
$ python soundcloud.py -h
usage: soundcloud.py [-h] [-s] [-j] url

Soundcloud - A tool for download track Soundcloud.

positional arguments:
  url           Url.

optional arguments:
  -h, --help    show this help message and exit

Options:
  -s , --save   Path to save
  -j, --json    Show json of info media.
  ```

- ***Install module***
  ```
  pip install -r requirements.txt
  ```
- ***Run*** 
  ```
  python soundcloud.py [url]
  ```

- ***All the track downloaded in folder DOWNLOAD at the same path***

# ***Options***
- `-s` or `--saved` : Saved file name.
- `-j` or `--json`  : Print json info.
- ***Some url is hls, need setup [ffmpeg](https://www.ffmpeg.org/)***

  
# ***Url Supported***
- Track url : ```https://soundcloud.com/<uploader>/<slug>```
- Playlist sets : ```https://soundcloud.com/<uploader>/sets/<slug>```
- Playlist tracks of user : 
    ```
    https://soundcloud.com/<name user>
    https://soundcloud.com/<name user>/popular-tracks
    https://soundcloud.com/<name user>/tracks
    https://soundcloud.com/<name user>/sets
    https://soundcloud.com/<name user>/reposts
    https://soundcloud.com/<name user>/albums
    ``` 

# ***Note***
  - [`facebook`](https://www.facebook.com/hatien.l0i2612/)
  - `hatienloi261299@gmail.com`