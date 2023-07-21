# Requirements

```Bash
pip3 install tldextract selenium
```

## Docker setup

```Bash
SS_EXPORT_PATH=/path/to/screenshot/dir/
cd profile_crawler
docker build -t profile-crawler
docker run -it -v "$SS_EXPORT_PATH":/data profile-crawler
```
Add `--rm` if you want it to be disposable (one-time task)


Test (inside docker container)
```Bash
python3 profile_crawler.py -mp 10 -d 2 -t 1 -ep '/data' -f './links.txt'
```

# Common usage

Crawling relevant and irrelevant pages together
```Bash
python3 profile_crawler.py -br -f links.txt -d 2 -mp 300 -ep /data -t `nproc`
```

Crawling relevant by providing list of URLs to collective page
```Bash
python3 profile_crawler.py -p -f links.txt -d 1 -ep /data -t `nproc`
```

Crawling relevant by providing list of direct URLs to profile page
```Bash
python3 profile_crawler.py -b -p -f links.txt -d 0 -ep /data -t `nproc`
```
