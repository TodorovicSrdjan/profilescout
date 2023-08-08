# Changelog

## v0.2.2

### Features
- implement web driver abstraction

## v0.2.1

### Features
- improve origin sublink filtering

### Fixes
- handle case when link key is missing
- fix case when there isn't any name candidate
- fix origin sublink filtering
- add missing not in condition sublink
- handle filtering URLs with IDs in path

## v0.2.0

### Features
- add custom width support
- add option to download page html
- improve url2path mapping
- add support for html info extract
- add extraction for custom fields
- improve info extraction
- add support for profile page scraping
- add detection of image tag changes
- detect & classify different types of links
- add better detection of profile images

### Fixes
- handle case when img model is not present
- fix problems with international num extract
- fix parsing of markdown links
- exclude js and css from data extraction
- fix context update with international numbers

## v0.1.0

### Features
- add functionality for detecting origin page

### Fixes
- add missing comma in relevant words
- make URL lower to match relevant word
- prioritize links in the whole visiting queue