import os
import re
import json
import string
import difflib
import urllib.parse

from bs4 import BeautifulSoup
from html2text import HTML2Text
from collections import defaultdict
from phonenumbers import PhoneNumberMatcher, PhoneNumberFormat, format_number, parse

from profilescout.link.utils import to_key, is_url, to_abs_path


PATTERNS = {'unwanted_tag__has_placeholder': r'(<\/?(?:b|i|strong|em|blockquote|h[1-6])\b[^>]*>)',
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


def _get_differences(different_lines):
    differences = []
    for line in different_lines:
        match_diff_line = re.search(PATTERNS['different_line'], line)
        if line.startswith('+') and match_diff_line:
            # get only the lines that differ from the lines on the base page

            line = match_diff_line.group(1)
            for tag in re.findall(PATTERNS['unwanted_tag__has_placeholder'], line, flags=re.DOTALL):
                line = line.replace(tag, '')

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


def _extract_differences(base_page, other_page):
    # Compare the pages using difflib
    different_lines = difflib.unified_diff(
        str(base_page).splitlines(),
        str(other_page).splitlines(),
        lineterm='',
    )
    return _get_differences(different_lines)


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
    if not must_find or len(sorted_word_pairs) == 0:
        return None
    # choose most occuring pair as person's name
    full_name = sorted_word_pairs[0][0]
    return f'{full_name[0]} {full_name[1]}'.title()


def _update_context(context, extracted_info, replacement):
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
        number_info['context'] = _update_context(text, phone_numbers, 'PHONE_NUMBER')
        for i, number in enumerate(phone_numbers):
            number = parse(number, country_code)
            try:
                phone_numbers[i] = format_number(number, PhoneNumberFormat.E164)
            except Exception:
                pass
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
        number_info['context'] = _update_context(text, phone_numbers, 'PHONE_NUMBER')
    return number_info


def extract_phone_numbers(text, country_code):  # TODO fix for national nums, e.g. '011/1234-567'
    number_info = {'numbers': [], 'context': text}
    international_numbers = extract_international_phone_numbers(text, country_code)
    number_info['numbers'].extend(international_numbers['numbers'])
    number_info['context'] = international_numbers['context']
    return number_info


def _process_links(match_md_link, resume_links, resume_emails, context):
    found_something = True
    for md_link in match_md_link:
        link = md_link[1].strip()
        if 'mailto:' in link:
            if link in resume_emails:
                found_something = False
            else:
                context = _update_context(context, f'[{md_link[0]}]({md_link[1]})', 'EMAIL')
                link = link.replace('mailto:', '').strip()
                resume_emails.append(link)
        else:
            url_parts = urllib.parse.urlsplit(link)
            encoded_query = urllib.parse.quote(url_parts.query, safe='=&')
            link = urllib.parse.urlunsplit(url_parts._replace(query=encoded_query))
            # find key
            key = md_link[0].strip()
            if is_url(key):
                key = to_key(link)
            # check if it is relative link
            elif re.search(r'^[^(www)|(http)].+?\..+(/.+)*$', link.lower()):
                key = 'this'
                # check if it is relative link to an image
                if re.search(r'^(images?/)?.*?\.(jpg|jpeg|png|svg|webp|gif|bmp|ppm)$', link.lower()):
                    key = 'images'

            if key == '':
                key = 'profile_picture'

            # add new link
            if key not in resume_links:
                resume_links[key] = link
            elif isinstance(resume_links[key], str):
                resume_links[key] = [link, resume_links[key]]
            else:
                resume_links[key].append(link)
            context = _update_context(context, f'[{md_link[0]}]({md_link[1]})', 'LINK')
    return {
        'found_something': found_something,
        'context': context}


def _post_processing(resume, name_candidates):
    if 'Source URL' in resume:
        resume['url'] = resume.pop('Source URL')
    # try to guess person's name
    possible_name = guess_name(name_candidates, must_find=True)
    if possible_name is not None:
        name = possible_name
        if 'Source text' in resume:
            link_text = resume.pop('Source text')
            name_ci = longest_common_substring(link_text, possible_name, case_sensitive=False)
            name_parts = name_ci.split()
            name = ' '.join([name_part.capitalize() for name_part in name_parts])
        resume['name'] = name
        # remove name instances from `other`
        if possible_name in resume['other']:
            resume['other'].remove(possible_name)
        if possible_name.upper() in resume['other']:
            resume['other'].remove(possible_name.upper())
        # check if profile image link is missing
        if 'profile_picture' not in resume['links']:
            first, last = possible_name.lower().split()
            if 'images' in resume['links']:
                for img_link in resume['links']['images']:
                    if 'images' in resume and (
                        first.lower() in img_link.lower() or last.lower() in img_link.lower()
                    ):
                        resume['links']['profile_picture'] = img_link
                        if isinstance(resume['links']['images'], str):
                            del resume['links']['images']
                        else:
                            resume['links']['images'].remove(img_link)
                        break
        # convert relative links to abs
        if 'url' in resume:
            url = resume['url']
            for key in ['this', 'images', 'profile_picture']:
                if key in resume['links']:
                    if key == 'profile_picture':
                        print(resume['links'][key])
                    if isinstance(resume['links'][key], str):
                        resume['links'][key] = to_abs_path('/' + resume['links'][key], url)
                    else:
                        resume['links'][key] = [to_abs_path('/' + link, url) for link in resume['links'][key]]
        # remove duplicates
        resume['emails'] = list(dict.fromkeys(resume['emails']))
        resume['other'] = list(dict.fromkeys(resume['other']))
        return resume


def _parse_differences(differences, country_code=None):
    '''returns resume information which is extracted from differences between pages'''
    resume = {
        'context': [],
        'emails': [],
        'links': dict(),
        'other': [],
        'phone_numbers': []
        }
    name_candidates = []
    for difference in differences:
        match_email = re.findall(PATTERNS['email'], difference)
        match_md_link = re.findall(PATTERNS['md_link'], difference)
        match_label_field = re.search(PATTERNS['label_field'], difference)
        match_label_field_with_value = re.search(PATTERNS['label_field_with_value'], difference)

        found_something = False
        context = difference
        # add numbers to resume
        number_info = extract_phone_numbers(difference, country_code)
        if len(number_info['numbers']) > 0:
            resume['phone_numbers'] = number_info['numbers']
            context = number_info['context']
            found_something = True
        # add links to resume
        if match_md_link:
            result = _process_links(match_md_link, resume['links'], resume['emails'], context)
            context = result['context']
            found_something = result['found_something']
        # add emails to resume
        # note: this has to go after md link match to avoid matching the same thing multiple times
        if match_email:
            found_something = True
            for email in match_email:
                resume['emails'].append(email)
                name_candidates.append(email)
                context = _update_context(context, email, 'EMAIL')
        # add anything else to resume
        if not found_something:
            if match_label_field_with_value:
                # add key-value pair as top-level info
                key = match_label_field_with_value.group(1)
                value = match_label_field_with_value.group(2)
                resume[key.strip()] = value.strip()
                context = _update_context(context, key, 'FIELD_KEY')
                context = _update_context(context, value, 'FIELD_VAL')
            elif not match_label_field:
                # add the rest
                resume['other'].append(difference)
                name_candidates.append(difference)
        if context != difference:
            resume['context'] += [context]
    final_resume = _post_processing(resume, name_candidates)
    return final_resume


def get_resume_info(base_page, page, country_code=None):
    '''Extract resume information by comparing to base page

    This is based on the fact that the pages on the same website mostly have the same layout.
    Only the fields for information were modified when comparing two profiles.

    Returns dictionary with identified and not identified field values
    '''
    differences = _extract_differences(base_page, page)
    return _parse_differences(differences, country_code)


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


def longest_common_substring(str1, str2, case_sensitive=True):
    m = len(str1)
    n = len(str2)
    if not case_sensitive:
        str1 = str1.lower()
        str2 = str2.lower()
    # create a table to store the lengths of common substrings
    table = [[0] * (n + 1) for _ in range(m + 1)]
    # variables to keep track of the longest common substring
    max_length = 0
    end_index = 0
    for i in range(1, m + 1):
        for j in range(1, n + 1):
            if str1[i - 1] == str2[j - 1]:
                table[i][j] = table[i - 1][j - 1] + 1
                if table[i][j] > max_length:
                    max_length = table[i][j]
                    end_index = i
    # extract the longest common substring
    longest_substring = str1[end_index - max_length: end_index]
    return longest_substring
