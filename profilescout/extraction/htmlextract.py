import os
import re
import json
import string
import difflib
import urllib.parse

from bs4 import BeautifulSoup
from html2text import HTML2Text
from collections import Counter
from phonenumbers import PhoneNumberMatcher, PhoneNumberFormat, format_number, parse

from profilescout.common.texthelpers import longest_common_substring, dl_distance
from profilescout.link.utils import to_key, is_url, to_abs_path
from profilescout.extraction.ner import NamedEntityRecognition


PATTERNS = {'unwanted_tag__has_placeholder': r'(<\/?(?:b|i|strong|em|blockquote|h[1-6])\b[^>]*>)',
            'md_link': r'(!?)\[([^\[\]]*?)\]\((.+?)\)',
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


ner = NamedEntityRecognition()


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


def _rank_name_candidate(candidate):
    parts = candidate.split()
    lenght = len(parts)
    if lenght in [2, 3, 4]:
        return 0
    if lenght == 1:
        return 1
    return 2


def guess_name(ner, txt, origin_link_text):
    '''Guess person's name using NER and text of the link that leads to this HTML page
    '''
    names = ner.get_names(txt)
    link_txt = origin_link_text.strip() if origin_link_text is not None and origin_link_text != '' else None

    if names is None or len(names) == 0:
        return link_txt

    norm_names = []
    for name in names:
        match = re.search(r'(?:\w{1,4}\.?\ )?(\w+?)(?:(?:\ \w{1,4}\.?)|(?:,\ \w+?,)|(?:\ \(\ ?\w+?\ ?\)))?\ ([\w\ -]+)', name)
        if match:
            norm_names.append(f'{match.group(1)} {match.group(2)}')
        else:
            norm_names.append(name)

    name_counts = Counter(norm_names).items()
    names_sorted = None
    if link_txt is None:
        names_sorted = sorted(name_counts, key=lambda x: (_rank_name_candidate(x[0]), -x[1]))
        name = names_sorted[0][0]
    else:
        names_sorted = sorted(name_counts, key=lambda x: (
            _rank_name_candidate(x[0]),
            -x[1],
            dl_distance(link_txt.lower(), x[0].lower()))
        )
        name = longest_common_substring(names_sorted[0][0], link_txt, case_sensitive=False)
    return name.title()


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


def _process_links(difference, resume_links, resume_emails, context, nested=False):
    match_md_link = re.findall(PATTERNS['md_link'], difference)
    found_something = bool(match_md_link)
    replacement = 'LINK'
    for md_link in match_md_link:
        link = md_link[2].strip()
        if 'mailto:' in link and link not in resume_emails:
            context = _update_context(context, f'[{md_link[1]}]({md_link[2]})', 'EMAIL')
            link = link.replace('mailto:', '').strip()
            if link not in resume_emails:
                resume_emails.append(link)
        else:
            url_parts = urllib.parse.urlsplit(link)
            encoded_query = urllib.parse.quote(url_parts.query, safe='=&')
            link = urllib.parse.urlunsplit(url_parts._replace(query=encoded_query))
            # find key
            key = md_link[1].strip()
            if is_url(key):
                key = to_key(link)
            # check if it is relative link
            elif re.search(r'^[^(www)|(http)].+?\..+(/.+)*$', link.lower()):
                key = 'this'
            # check if it is link to an image
            if (
                re.search(r'^(images?/)?.*?\.(jpg|jpeg|png|svg|webp|gif|bmp|ppm)$', link.lower())
                or re.search(r'^data:image/.*$', link.lower())
            ):
                key = 'images'
            if nested:
                key = key.replace(replacement, '')
                replacement = 'NESTED_LINKS'
            # add new link
            if key not in resume_links:
                resume_links[key] = link
            elif isinstance(resume_links[key], str):
                resume_links[key] = [link, resume_links[key]]
            elif link not in resume_links[key]:
                resume_links[key].append(link)

            context = _update_context(context, f'{md_link[0]}[{md_link[1]}]({md_link[2]})', replacement)
            subresult = _process_links(context, resume_links, resume_emails, context, nested=True)
            if subresult['found_something']:
                context = subresult['context']

    return {
        'found_something': found_something,
        'context': context}


def _post_processing(resume):
    if 'Source URL' in resume:
        resume['url'] = resume.pop('Source URL')
    link_text = ''
    if 'Source text' in resume:
        link_text = resume.pop('Source text')
    # try to guess person's name
    name = guess_name(ner, '\n'.join(resume['other']), link_text)
    if name is not None:
        resume['name'] = name
        # remove name instances from `other`
        if name in resume['other']:
            resume['other'].remove(name)
        if name.upper() in resume['other']:
            resume['other'].remove(name.upper())
        # find and add profile page
        email_user_parts = [email.split('@')[0] for email in resume['emails']]
        email_parts = [
            part
            for parts in [
                re.split(r'[' + re.escape(string.punctuation) + ']', user_part)
                for user_part in email_user_parts
            ] if parts
            for part in parts
        ]
        name_parts = name.lower().split() + email_parts
        if 'images' in resume['links']:
            img_links = resume['links']['images']
            if isinstance(resume['links']['images'], str):
                img_links = [resume['links']['images']]
            for img_link in img_links:
                img_link_lwr = img_link.lower()
                img_link_clean = ''.join(re.split(r'[' + re.escape(string.punctuation) + ']', img_link_lwr))
                for name_part in name_parts:
                    if name_part in img_link_clean:
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
                    if isinstance(resume['links'][key], str):
                        resume['links'][key] = to_abs_path(resume['links'][key], url)
                    else:
                        resume['links'][key] = [to_abs_path(link, url) for link in resume['links'][key]]
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
    for difference in differences:
        match_email = re.findall(PATTERNS['email'], difference)
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
        result = _process_links(difference, resume['links'], resume['emails'], context)
        found_links = len(result) != 0
        if found_links:
            context = result['context']
            found_something = result['found_something']
        # add emails to resume
        # note: this has to go after md link match to avoid matching the same thing multiple times
        if match_email:
            found_something = True
            for email in match_email:
                if email not in resume['emails']:
                    resume['emails'].append(email)
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
                if difference not in resume['other']:
                    resume['other'].append(difference)
        if context != difference:
            resume['context'] += [context]
    final_resume = _post_processing(resume)
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
        country_code = country_code.split('-')[-1].upper() if country_code is not None else None

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
