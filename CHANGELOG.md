# Changelog

## v0.3.2

### Features
- add param for ignoring file presence url2fp
- create abstraction over classifiers

### Fixes
- remove LongFilenameException
- issues with missing classifier
- make 'www' irrelevant for url validation

## v0.3.0

### Features
- treat links with or w/o 'www' as the same
- improve finding the most common fmt
- exclude header/footer links in link extract
- add support for flexible and custom crawl
- add text property to WebElement
- add source URL and text to extracted info

### Fixes
- exclude links without common subdomain
- escape format regex pattern
- make relevant words URL-safe
- make extracted links URL-safe
- don't add 'other' info to context

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