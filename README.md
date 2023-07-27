# About

**Profile Page Kit** is a versatile Python package that offers crawling and detection capabilities for profile pages on any given website. By leveraging its robust search functionality and machine learning, this tool crawls the provided URL and identifies the URLs of profile pages within the website. Profile Page Kit offers a convenient and effective solution for extracting user profiles, gathering valuable information, and performing targeted actions on profile pages. With its streamlined approach, this tool simplifies the process of locating and accessing profile pages, making it an invaluable asset for data collection, web scraping, and analysis tasks.

# Requirements

Third-Party Python packages
* `tldextract`
* `selenium`

## Docker setup

Execute this in project's directory
```Bash
SS_EXPORT_PATH="/path/to/screenshot/dir/"
docker build -t profilescout
docker run -it -v "$SS_EXPORT_PATH":/data profilescout
```
Add `--rm` if you want it to be disposable (one-time task)

Test (inside docker container)
```Bash
python3 src/profilescout/main.py -mp 10 -d 2 -t 1 -ep '/data' -f './links.txt'
```

# Common usage

Crawling relevant and irrelevant pages together
```Bash
python3 src/profilescout/main.py -br -f links.txt -d 2 -mp 300 -ep /data -t `nproc`
```

Crawling relevant by providing list of URLs to collective page
```Bash
python3 src/profilescout/main.py -p -f links.txt -d 1 -ep /data -t `nproc`
```

Crawling relevant by providing list of direct URLs to profile page
```Bash
python3 src/profilescout/main.py -b -p -f links.txt -d 0 -ep /data -t `nproc`
```
