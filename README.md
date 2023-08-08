# Profile Scout

![License](https://img.shields.io/github/license/todorovicsrdjan/profilescout)
![Last commit](https://img.shields.io/github/last-commit/todorovicsrdjan/profilescout/master)
![Repo size](https://img.shields.io/github/repo-size/todorovicsrdjan/profilescout)

**Table of Contents**
* [About](#about)
* [Capabilities](#capabilities)
* [Common Use Cases](#common-use-cases)
  * [Scraping](#scraping)
  * [Profile related tasks](#profile-related-tasks)
  * [Information extraction](#information-extraction)
* [Setup](#setup)
  * [Host Setup](#host-setup)
  * [Docker Setup](#docker-setup)
  * [Used third-party packages](#used-third-party-packages)
* [Possibilities for future improvements](#possibilities-for-future-improvements)
* [Contributing](#contributing)

# About

**Profile Scout** is a versatile Python package that offers scraping and detection capabilities for profile pages on any given website, including support for information extraction. By leveraging its robust search functionality and machine learning, this tool crawls the provided URL and identifies the URLs of profile pages within the website. Profile Scout offers a convenient solution for extracting user profiles, gathering valuable information, and performing targeted actions on profile pages. With its streamlined approach, this tool simplifies the process of locating and accessing profile pages, making it an invaluable asset for data collection, web scraping, and analysis tasks. Additionally, it supports information extraction techniques, allowing users to extract specific data from profile pages efficiently.

Profiel Scout can be useful to: 
1. Investigators and [OSINT Specialists](https://en.wikipedia.org/wiki/Open-source_intelligence) (information extraction, creating information graphs, ...)
2. [Penetration Testers](https://en.wikipedia.org/wiki/Penetration_test) and Ethical Hackers/[Social Engineers](https://en.wikipedia.org/wiki/Social_engineering_(security)) (information extraction, reconnaissance, profile building)
3. Scientists and researchers (data engineering, data science, social science, research)
4. Companies (talent research, marketing, contact acquisition/harvesting)
5. Organizations (contact acquisition/harvesting, data collecting, database updating)

# Capabilities

Profile Scout is mainly a crawler. For given URL, it will crawl the site and perform selected actions.
If the file with URLs is provided, each URL will be processed in seperate thread.

Main features:
1. Flexible and controlled page scraping (HTML, page screenshot, or both)
2. Detecting and scraping profile pages during the crawling process
3. Locating the collective page from which all profile pages originate.
4. Information extraction from HTML files

Options:
```
-h, --help            
    show this help message and exit
    
--url URL             
    URL of the website to crawl
    
-f URLS_FILE_PATH, --file URLS_FILE_PATH
    Path to the file with URLs of the websites to crawl
    
-D DIRECTORY, --directory DIRECTORY
    Extract data from HTML files in the directory. To avoid saving output, set '-ep'/'--export-path' to ''
    
-a {scrape_pages,scrape_profiles,find_origin}, --action {scrape_pages,scrape_profiles,find_origin}
    Action to perform at a time of visiting the page (default: scrape_pages)
    
-b, --buffer          
    Buffer errors and outputs until crawling of website is finished and then create logs
    
-br, --bump-relevant  
    Bump relevant links to the top of the visiting queue (based on RELEVANT_WORDS list)
    
-ep EXPORT_PATH, --export-path EXPORT_PATH
    Path to destination directory for exporting
    
-ic {scooby,batman}, --image-classifier {scooby,batman}
    Image classifier to be used for identifying profile pages (default: scooby)
    
-cs CRAWL_SLEEP, --crawl-sleep CRAWL_SLEEP
    Time to sleep between each page visit (default: 2)
    
-d DEPTH, --depth DEPTH
    Maximum crawl depth (default: 2)
    
-if, --include-fragment
    Consider links with URI Fragment (e.g. http://example.com/some#fragment) as seperate page
    
-ol OUT_LOG_PATH, --output-log-path OUT_LOG_PATH
    Path to output log file. Ignored if '-f'/'--file' is used
    
-el ERR_LOG_PATH, --error-log-path ERR_LOG_PATH
    Path to error log file. Ignored if '-f'/'--file' is used
    
-so {all,html,screenshot}, --scrape-option {all,html,screenshot}
    Data to be scraped (default: all)
                
-t MAX_THREADS, --threads MAX_THREADS
    Maximum number of threads to use if '-f'/'--file' is provided (default: 4)
    
-mp MAX_PAGES, --max-pages MAX_PAGES
    Maximum number of pages to scrape and page is considered scraped if the action is performed successfully (default: unlimited)
    
-p, --preserve        
    Preserve whole URI (e.g. 'http://example.com/something/' instead of 'http://example.com/')

-r RESOLUTION, --resolution RESOLUTION
    Resolution of headless browser and output images. Format: WIDTHxHIGHT (default: 2880x1620)

Full input line format is: '[DEPTH [CRAWL_SLEEP]] URL"

DEPTH and CRAWL_SLEEP are optional and if a number is present it will be consider as DEPTH.
For example, "3 https://example.com" means that the URL should be crawled to a depth of 3.

If some of the fields (DEPTH or CRAWL_SLEEP) are present in the line then corresponding argument is ignored.

Writing too much on the storage drive can reduce its lifespan. To mitigate this issue, if there are more than
30 links, informational and error messages will be buffered and written at the end of
the crawling process.

RELEVANT_WORDS=['profile', 'user', 'users', 'about-us', 'team', 'employees', 'staff', 'professor', 
                'profil', 'o-nama', 'zaposlen', 'nastavnik', 'nastavnici', 'saradnici', 'profesor', 'osoblje', 
                'запослен', 'наставник', 'наставници', 'сарадници', 'професор', 'особље']
```

# Common Use Cases

Note: Order of arguments/switches doesn't matter

## Scraping

Scrape the URL up to a depth of 2 (`-d`) or a maximum of 300 scraped pages (`-mp`), 
depending on which comes first. Store scraped data at `/data` (`-ep`)
```Bash
python3 main.py --url https://example.com -d 2 -mp 300 -ep /data
```

Scrape HTML (`-so html`) for every page up to a depth of 2 for the list of URLs (`-f`). 
Number of threads to be used is set with `-t`
```Bash
python3 main.py -ep /data -t `nproc` -f links.txt -d 2 -so html
```

Start scraping screenshots from specific page (`-p`). It is import to note here that
without `-p`, program would ignore full path, to be precise `/about-us/meet-the-team/` part
```Bash
python3 main.py -p --url https://www.wowt.com/about-us/meet-the-team/ -mp 4 -so screenshot
```

Scrape each website in the URLs list and postpone writing to the storge disk (by using buffer, `-b`)
```Bash
python3 main.py -b -t `nproc` -f links.txt -d 0 -ep /data
```

## Profile related tasks

Scrape profile pages (`-a scrape_profiles`) and prioritize links that are relevant to some specific domain (`-br`). 
For example, if we were searching for profile pages of professors we would like to give priority to links that 
contain related terms which could lead us to the profile page. Note: you can change it in file 
[constants.py](./profilescout/common/constants.py#34)
```Bash
python3 main.py -br -t `nproc` -f links.txt -a scrape_profiles -mp 30
```

Find and screenshot profile, store it as 600x400 (`-r`) image and then wait (`-cs`) 30 seconds before moving to the next profile
```Bash
python3 main.py -br -t `nproc` -f links.txt -a scrape_profiles -mp 1000 -d 3 -cs 30 -r 600x400
```

Locate the origin page of profile pages (`-a locate_origin`) with classifier called `batman` (`-ic batman`).
Note that visited pages are lond so in can be used for something like scanning the website
```Bash
python3 main.py -t `nproc` -f links.txt -a locate_origin -ic batman
```

## Information extraction

Extract information (`-D`) contained in profile HTMLs that are located at `/data` and store it at `~/results` (`-ep`)
```Bash
python3 main.py -D /data -ep ~/results
```

# Setup

## Host setup

1. Create virtual environment (optional, but recommended)
```Bash
python3 -m venv /path/to/some/dir
```

2. Activate virtual environment (skip if you skipped the first step)
```Bash 
source /path/to/some/dir/bin/activate
```

3. Install requirements
```Bash
pip3 install -r requirements
```

4. Download models for classification (this is **required** step if you want to crawl with profile detection)
```
cd /path/to/some/dir
mkdir classifiers
wget https://huggingface.co/tsrdjan/scooby/resolve/main/scooby.h5
```

5. Explore
```
cd ..
python3 profilescout/main.py -h
```

## Docker setup

1. Create image and run container. Execute this in project's directory
```Bash
mkdir "/path/to/screenshot/dir/"            # if it does not exist
# this line may differ depending on your shell, 
# so check the documentation for the equivalent file to .bashrc
echo 'export SS_EXPORT_PATH="/path/to/screenshot/dir/"' >> ~/.bashrc
docker build -t profilescout .
docker run -it -v "$SS_EXPORT_PATH":/data profilescout
```

Add `--rm` if you want it to be disposable (one-time task)

2. Test deployment (inside docker container)
```Bash
python3 profilescout/main.py -mp 4 -t 1 -ep '/data' -p --url https://en.wikipedia.org/wiki/GNU
```

## Used third-party packages
* `bs4`
* `html2text`
* `numpy`
* `pillow`
* `phonenumbers`
* `selenium`
* `tensorflow`
* `tldextract` 

# Possibilities for future improvements

* Classification
  * Profile classification based on existing data (without crawling)
  * Classification using HTML and images, as well as the selection of appropriate classifiers
* Scraping
  * Intelligent downloading of files through links available on the profile page
* Crawling
  * Support for scraping using proxies.
* Crawling actions
  * Ability to provide custom actions
  * Actions before and after page loading.
  * Multiple actions for each stage of page processing (before, during, and after access).
* Crawling strategy
  * Ability to provide custom heuristics
  * Ability to choose crawling strategy (link filters, etc.)
  * Support for deeper link bump
  * Selection of relevant words using CLI
* Usability
  * Saving progress and the ability to resume
  * Increased automation (if the profile is not found at depth DEPTH, increase the depth and continue).
* Extraction
  * Support for national numbers, e.g. `011/123-4567`
  * Experiment with lightweight LLMs
  * Experiment with Key-Value extraction and Layout techniques like [LayoutLM](https://arxiv.org/abs/1912.13318)

# Contributing

If you discover a bug or have a feature idea, feel free to open an issue or PR.  
Any improvements or suggestions are welcome!