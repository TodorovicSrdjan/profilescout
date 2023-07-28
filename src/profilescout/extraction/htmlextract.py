import os
import re
import json
import string
import difflib

from bs4 import BeautifulSoup
from html2text import HTML2Text
from collections import defaultdict
from phonenumbers import PhoneNumberMatcher, PhoneNumberFormat, format_number, parse

from link.utils import to_key

TAGS_TO_EXCLUDE = ['b', 'i', 'strong', 'em', 'blockquote',
                   'h1', 'h2', 'h3', 'h4', 'h5', 'h6']

PATTERNS = {'unwanted_tag__has_placeholder': r'(?:<PLACEHOLDER.*?>)?(.*?)(?:</PLACEHOLDER>)?',
            'md_link': r'\[(.*?)\]\((.+?)\)',
            'email': r'(?:[a-z0-9_\.\+-]+)@(?:[\da-z\.-]+)\.(?:[a-z\.]{2,6})',
            'different_line': r'^\+*([^+]*\w+.*)$',
            'label_field': r'^\w.*:$',
            'label_field_with_value': r'^(\w.*?):(.*\w.*)$',
            'repetetive_punct': f'[ {re.escape(string.punctuation)}]+',
            'repeating_whitespace': r'(?:(\ )+)|(?:(\t)+)|(?:(\n)+)|(?:(\r)+)|(?:(\f)+)',
            'number': r'((?:\(?(?:00|\+)(?:[1-4]\d\d|[1-9]\d?)\)?)?[\-\.\ \\\/]?'  # TODO fix for md links
                                    + r'((?:\(?\d{1,}\)?[\-\.\ \\\/]?){0,}'
                                    + r'(?:#|ext\.?|extension|x)?[\-\.\ \\\/]?\d+)?)'
            }


def __get_differences(different_lines):
    differences = []
    for line in different_lines:
        match_diff_line = re.search(PATTERNS['different_line'], line)
        if line.startswith('+') and match_diff_line:
            # get only the lines that differ from the lines on the base page

            line = match_diff_line.group(1)
            for tag in TAGS_TO_EXCLUDE:
                pattern = PATTERNS['unwanted_tag__has_placeholder'].replace('PLACEHOLDER', tag)
                line = re.sub(pattern, r'\1', line, flags=re.DOTALL)

            # this is not documented 'html2text' usage
            # 'html2text.html2text' does:
            # ```
            #   h = HTML2Text(baseurl=baseurl)
            #   return h.handle(html)
            # ```
            # and since 'body_width' can be only provided from CLI, default value (78) is used
            h2t = HTML2Text()
            h2t.body_width = 0
            line = h2t.handle(line)  # convert to md

            line = line.replace('*', '')
            line = line.strip()
            if line not in ['', '#']:
                lines = line.split('\n')
                lines = [line.strip() for line in lines]
                differences.extend(lines)
    return differences


def __extract_differences(base_page, other_page):
    # Compare the pages using difflib
    different_lines = difflib.unified_diff(
        str(base_page).splitlines(),
        str(other_page).splitlines(),
        lineterm='',
    )
    return __get_differences(different_lines)


def guess_name(parts, threshold=2, must_find=False):
    '''Guess person's name based on frequency of words

    Parameter threshold represents number of occurences of 2 words
    after which they will be considered as first and last name.
    '''
    parts_flat = [part for part in parts if isinstance(part, str)]
    for part in parts:
        if isinstance(part, dict):
            parts_flat.extend(*part.items())

    # preprocess data
    words = []
    for part in parts_flat:
        splitted = re.split(PATTERNS['repetetive_punct'], part)
        words += [word for word in splitted if word != '']

    # create a dictionary to count word pairs
    word_pair_original = dict()
    word_pair_counts = defaultdict(int)
    for i in range(len(words) - 1):
        if words[i] == '' or words[i+1] == '':
            continue
        word_pair = (words[i].lower(), words[i+1].lower())
        word_pair_original[word_pair] = (words[i], words[i+1])
        word_pair_counts[word_pair] += 1

    # sort the dictionary by counts in descending order
    sorted_word_pairs = sorted(
        word_pair_counts.items(),
        key=lambda x: x[1],
        reverse=True
    )

    # filter and return first and last name word pairs
    for word_pair, count in sorted_word_pairs:
        og_first_name = word_pair_original[word_pair][0]
        og_last_name = word_pair_original[word_pair][1]
        if og_first_name[0].isupper() and og_last_name[0].isupper():
            if count >= threshold:
                return ' '.join(word_pair).title()
    if not must_find or len(sorted_word_pairs) > 0:
        return None
    # choose most occuring pair as person's name
    full_name = sorted_word_pairs[0]
    return f'{full_name[0]} {full_name[1]}'.title()


def __update_context(context, extracted_info, replacement):
    # remove found info from context
    if isinstance(extracted_info, str):
        extracted_info = [extracted_info]
    for info in extracted_info:
        context = context.replace(info, replacement)

    return context


def extract_international_phone_numbers(text, country_code):
    number_info = {'numbers': [], 'context': text}
    phone_numbers = []
    for number in PhoneNumberMatcher(text, country_code):
        phone_numbers.append(number.raw_string)
    if len(phone_numbers) > 0:
        if country_code is not None:
            for i, number in enumerate(phone_numbers):
                number_info['context'] = __update_context(text, phone_numbers, 'PHONE_NUMBER')
                number = parse(number, country_code)
                phone_numbers[i] = format_number(number, PhoneNumberFormat.E164)
        number_info['numbers'] = phone_numbers
    return number_info


def extract_national_phone_numbers(text):
    number_info = {'numbers': [], 'context': text}
    phone_numbers = []
    match_number = re.findall(PATTERNS['number'], text)
    if match_number:
        phone_numbers = [num_match[0] for num_match in match_number if num_match[0] != '']
    # add numbers if country code is not present
    if len(phone_numbers) > 0:
        number_info['numbers'] = phone_numbers
        number_info['context'] = __update_context(text, phone_numbers, 'PHONE_NUMBER')
    return number_info


def extract_phone_numbers(text, country_code):  # TODO fix for national nums, e.g. '011/1234-567'
    number_info = {'numbers': [], 'context': text}
    international_numbers = extract_international_phone_numbers(text, country_code)
    number_info['numbers'].extend(international_numbers['numbers'])
    number_info['context'] = international_numbers['context']
    return number_info


def __parse_differences(differences, country_code=None):
    '''returns resume information which is extracted from differences between pages'''
    resume = dict()
    resume['context'] = []
    resume['emails'] = []
    resume['links'] = []
    resume['other'] = []
    resume['phone_numbers'] = []
    name_candidates = []
    for difference in differences:
        match_email = re.findall(PATTERNS['email'], difference)
        match_md_link = re.findall(PATTERNS['md_link'], difference)
        match_label_field = re.search(PATTERNS['label_field'], difference)
        match_label_field_with_value = re.search(PATTERNS['label_field_with_value'], difference)

        found_something = False
        context = difference
        number_info = extract_phone_numbers(difference, country_code)
        if len(number_info['numbers']) > 0:
            resume['phone_numbers'] = number_info['numbers']
            context = number_info['context']
            found_something = True
        if match_md_link:
            for md_link in match_md_link:
                link = md_link[1].strip()
                if 'mailto:' in link:
                    if link not in resume['emails']:
                        context = __update_context(context, f'[{md_link[0]}]({md_link[1]})', 'EMAIL')
                        link = link.replace('mailto:', '').strip()
                        resume['emails'].append(link)
                        found_something = True
                else:
                    key = md_link[0].strip()
                    if key == '':
                        key = to_key(link)
                    link = {key: link}
                    resume['links'].append(link)
                    context = __update_context(context, f'[{md_link[0]}]({md_link[1]})', 'LINK')
                    found_something = True
        # note that this has to go after md link match to avoid matching same thing multiple times
        if match_email:
            found_something = True
            for email in match_email:
                resume['emails'].append(email)
                name_candidates.append(email)
                context = __update_context(context, email, 'EMAIL')
        if not found_something:
            if match_label_field_with_value:
                key = match_label_field_with_value.group(1)
                value = match_label_field_with_value.group(2)
                resume[key.strip()] = value.strip()
                context = __update_context(context, key, 'FIELD_KEY')
                context = __update_context(context, value, 'FIELD_VAL')
            elif not match_label_field:
                resume['other'].append(difference)
                name_candidates.append(difference)
        resume['context'] += [context]
    # try to guess person's name
    possible_name = guess_name(name_candidates, must_find=True)
    if possible_name is not None:
        if possible_name in resume['other']:
            resume['other'].remove(possible_name)
        if possible_name.upper() in resume['other']:
            resume['other'].remove(possible_name.upper())
        resume['name'] = possible_name
        resume['emails'] = list(dict.fromkeys(resume['emails']))
        resume['other'] = list(dict.fromkeys(resume['other']))
    return resume


def get_resume_info(base_page, page, country_code=None):
    '''Extract resume information by comparing to base page

    This is based on the fact that the pages on the same website mostly have the same layout.
    Only the fields for information were modified when comparing two profiles.

    Returns dictionary with identified and not identified field values
    '''
    differences = __extract_differences(base_page, page)
    return __parse_differences(differences, country_code)


def get_resumes(pages, country_code=None):
    assert isinstance(pages, list), 'Parameter \'pages\' must be an list instance'
    assert len(pages) > 1, 'Number of pages has to be greater then 1'

    parsed_pages = []
    for page in pages:
        soup = BeautifulSoup(page, 'html.parser')
        # remove javascipt and css code
        for tag in soup.find_all("script"):
            soup.script.decompose()
        for tag in soup.find_all("style"):
            soup.style.decompose()
        parsed_pages.append(soup)
    base_page = parsed_pages[0]
    other_pages = parsed_pages[1:]
    resumes = dict()

    # if country_code is not set, try to infer it from html
    if country_code is None:
        country_code = base_page.html.get('lang')
        country_code = country_code.upper() if country_code is not None else None

    # charset = base_page.meta.get('charset')

    for i, page in enumerate(other_pages):
        key = str(i)
        resumes[key] = get_resume_info(base_page, page, country_code)

    key = len(resumes)
    resumes[key] = get_resume_info(other_pages[0], base_page, country_code)
    return resumes


def export_resumes(resumes, export_path, export_method):
    if export_method == 'json':
        with open(os.path.join(export_path, 'resumes.json'), 'w') as f:
            f.write(resumes)


def get_resumes_from_dir(dir_path, export_path=None, export_method='json'):
    profile_pages = []
    for root, _, files in os.walk(dir_path):
        for file in files:
            with open(os.path.join(root, file), 'r') as f:
                profile_pages.append(f.read())
    resumes = get_resumes(profile_pages)
    pretty_resumes = json.dumps(resumes, indent=4)
    if export_path is not None:
        export_resumes(''.join(pretty_resumes), export_path, export_method)
    return pretty_resumes
