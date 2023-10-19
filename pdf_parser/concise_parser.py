# Refining the function to extract fields and subfields information with improved parsing
import argparse
import json
import warnings
from typing import Tuple, Optional

import fitz
from pdf_parser.models import UnimarcField, Indicator, Code, Subfield, Position
import re


HEADER_PATTERN = re.compile(r'^\s*UNIMARC\sConcise\s\(2008\)\s*$', re.I | re.M)
FOOTER_PATTERN = re.compile(r'^\s\d{1,2}\s?/76\s*$', re.I | re.M)


def form_regex_pattern(field_name: str) -> str:
    return (re.sub(r'\s+', ' ', field_name)
            .replace(' ', '\\s*')
            .replace('(', '\\(')
            .replace(')', '\\)')
            .replace('[', '\\[')
            .replace(']', '\\]')
            .replace('-', '[\\-\\–]')
            .replace('$', '\\$'))


def get_field_text(field_name: str,
                   next_field_name: str,
                   doc: fitz.Document,
                   starting_page: int,
                   max_pages: int = 580,
                   is_last: bool = False) -> Tuple[str, int]:
    field_name = form_regex_pattern(field_name)
    next_field_name = form_regex_pattern(next_field_name) if next_field_name is not None else None

    field_text = ''

    # print('Searching for', field_name)
    i = starting_page

    for i in range(starting_page, max_pages):
        # first we have to find the field name in the document, and only then cn we start appending to the field text
        page_text = doc[i].get_text()

        header_row = HEADER_PATTERN.search(page_text)
        if header_row is None or header_row.group(0) is None:
            raise Exception(f'Page {i} not supported')

        page_text = page_text.replace(header_row.group(0), '', 1)

        footer_row = FOOTER_PATTERN.search(page_text)
        if footer_row is None or footer_row.group(0) is None:
            raise Exception(f'Page {i} not supported')

        page_text = page_text.replace(footer_row.group(0), '', 1)

        # if the page contains field name, check this page
        field_name_pattern = re.compile(rf'^\s*(?P<field_name>{field_name})\s+(?:\(.*?\))?\s*[I1l]nd[i1l]cator\s*(s|[1l])\s*:?', re.I | re.M | re.S)

        search_result = field_name_pattern.search(page_text)
        if search_result is None and field_text == '':
            continue

        if search_result is not None and field_text == '':
            field_name_start = search_result.start('field_name')
            page_text = page_text[field_name_start:]

        if next_field_name is None:
            field_text += page_text
            continue

        if is_last:
            next_field_name_pattern = re.compile(rf'^\s*(?P<next_field_name>{next_field_name})', re.I | re.M)
        else:
            next_field_name_pattern = re.compile(rf'^\s*(?P<next_field_name>{next_field_name})\s+(?:\(.*?\))?\s*[I1l]nd[i1l]cator\s*(s|[1l])\s*:?',
                                                 re.I | re.M | re.S)

        search_result = next_field_name_pattern.search(page_text)
        if search_result is not None:
            next_field_name_start = search_result.start('next_field_name')
            field_text += page_text[:next_field_name_start]
            break

        field_text += page_text

    return field_text, i


def get_occurrence(field_name: str, text: str) -> (bool, bool):
    """
    Gets occurrence of the field
    :param text:
    :return: (optional, repeatable)
    """
    # optionality and repeatability are to be found in parentheses directly after the field name
    # e.g. 100 General Processing Data (Mandatory, Not repeatable) or 100 General Processing Data (Repeatable), where
    # optionality is optional by default is nothing is mentioned. Repeatability is always specified

    # first find the field name, which should technically be the first thing in the text
    field_name = form_regex_pattern(field_name)

    field_name_pattern = re.compile(rf'^\s*(?P<field_name>{field_name})\s+(\(.*?\))', re.I | re.M | re.S)
    search_result = field_name_pattern.search(text)
    if search_result is None:
        warnings.warn(f'Field {field_name} appears not to have occurrence information')
        return False, False

    # so the second group is this (Mandatory, Not repeatable) or (Repeatable)
    occurrence_text = search_result.group(2)

    # first check if it says Mandatory
    mandatory_pattern = re.compile(r'Mandatory', re.IGNORECASE)
    mandatory_search_result = mandatory_pattern.search(occurrence_text)

    optional = mandatory_search_result is None

    # now check if it says Not repeateable or Non-repeateable
    non_repeatable_pattern = re.compile(r'(Not\s+|Non(\s?|\s*-\s*)?)repeatable', re.IGNORECASE)
    non_repeatable_search_result = non_repeatable_pattern.search(occurrence_text)

    repeatable = non_repeatable_search_result is None

    return optional, repeatable


def check_blank_indicator(indicator: str) -> bool:
    """
    Checks if the indicator is blank
    :param indicator:
    :return:
    """
    blank_pattern = re.compile(r'blank', re.I)
    search_result = blank_pattern.search(indicator)
    return search_result is not None


def get_indicator_codes(indicator_code_content: str) -> Optional[list]:
    """
    Gets indicator codes from indicator.
    :param indicator_code_content:
    :return:
    """
    indicator_code_content = indicator_code_content.strip()
    indicator_codes = []

    indicator_code_pattern = re.compile(r'(?P<code>[#\d])\s(?P<label>.*?)(?=^[#\d]|\Z)', re.MULTILINE | re.DOTALL)

    search_results = indicator_code_pattern.finditer(indicator_code_content)

    for search_result in search_results:
        indicator_code = Code()
        indicator_code.id = search_result.group('code').strip()
        indicator_code.label = search_result.group('label').strip()
        indicator_codes.append(indicator_code)

    return indicator_codes


def get_indicator_data(indicator_content: str) -> Optional[Indicator]:
    """
    Gets data from indicator
    :param indicator_content:
    :return:
    """
    indicator_content = indicator_content.strip()
    indicator_data = Indicator()

    indicator_pattern = re.compile(r'^(?P<indicator_label>.+?)\s*(?=\n\s*[#\d])', re.DOTALL)
    search_result = indicator_pattern.search(indicator_content)

    if search_result is None:
        # this shouldn't happen now
        return None

    indicator_data.label = search_result.group('indicator_label').strip()

    # replace the indicator label with empty string
    indicator_code_content = indicator_content.replace(indicator_data.label, '', 1)
    indicator_data.codes = get_indicator_codes(indicator_code_content)

    return indicator_data


def get_indicators(text: str) -> Tuple[Optional[Indicator], Optional[Indicator]]:

    indicators = [None, None]

    # it's either in form of Indicators: blank\nSubfield codes:... or Indicator1: something\nIndicator2: something
    # so we need to check for both
    # first check for Indicators: blank\nSubfield codes:... this is only in case there are no indicators
    indicators_blank_pattern = re.compile(r'^\s*[I1l]ndicators:?\s+(blank|none)\s*$', re.I | re.M)
    search_result = indicators_blank_pattern.search(text)

    if search_result is not None:
        return None, None

    # and now we check for separate indicators. first we get all the contents for indicator 1
    # (\r|\n|\r\n)\s*Indicator\s*[1l]:\s+(?P<indicator_content>.*?)\s*(#|\d)
    indicator_1_pattern = re.compile(r'(\r|\n|\r\n)\s*[I1l]ndicator\s*[1l]:?\s+'
                                     r'(?P<indicator_content>.*?)\s+[I1l]ndicator 2:?',
                                     re.I | re.S)
    search_result = indicator_1_pattern.search(text)

    if search_result is None:
        # this shouldn't happen now
        return None, None

    indicator_1_content = search_result.group('indicator_content')

    if check_blank_indicator(indicator_1_content):
        indicators[0] = None
    else:
        indicators[0] = get_indicator_data(indicator_1_content)

    indicator_2_pattern = re.compile(r'(\r|\n|\r\n)\s*[I1l]ndicator\s*2:?'
                                     r'\s+(?P<indicator_content>.*?)\s+Subfie[I1l]d codes:?',
                                     re.I | re.S)
    search_result = indicator_2_pattern.search(text)

    if search_result is None:
        # this shouldn't happen now
        return None, None

    indicator_2_content = search_result.group('indicator_content')

    if check_blank_indicator(indicator_2_content):
        indicators[1] = None
    else:
        indicators[1] = get_indicator_data(indicator_2_content)

    return indicators[0], indicators[1]


def get_position_codes(code_content: str, code_length=1) -> Optional[list[Code]]:
    # position codes have a form \w{position_length}\s*=\s*Explanation till another code sign
    # so if a position is of multiple characters as if in 10-12, then we should expect that we have
    # two character long codes. however it might also happen that we have something like code *to* code
    # which would then make it a little more difficult to generate all the codes
    # or we could have code-code

    code_pattern = re.compile(rf'(?P<code>.{{1,{code_length}}})\s*=\s*(?P<label>.*?)(?=(?:^.{{1,{code_length}}}\s*=)|\Z)', re.MULTILINE | re.DOTALL)

    search_results = code_pattern.finditer(code_content)

    codes = []

    for search_result in search_results:
        code = Code()
        code.id = search_result.group('code').strip()
        code.label = search_result.group('label').strip()
        codes.append(code)

    return codes


def get_subfields(text: str) -> Optional[list[Subfield]]:
    # first we want to get the text between Subfield codes: and the end of the text
    subfields_pattern = re.compile(r'Subfie[I1l]d\s*codes:?\s+(?P<subfields_content>.*?)\s*$', re.I | re.S)
    search_result = subfields_pattern.search(text)

    if search_result is None:
        return None

    subfields_content = search_result.group('subfields_content')

    subfields = []

    # first, we get subfields which are in the form of $a Something,
    # and then we'll get the subfield positions which are in the form of $a/7 Something or $a/7-9 Something
    # after that, the subfield positions will be assigned to the subfields
    # for some positions there are also codes which are in the form of aa = Something1\nab = Something2

    # ! or what can apparently happen is that it can also be $a to $c. this is going to be done manually
    subfield_pattern = re.compile(r'^\s*(?P<subfield_id>\$.)\s+(?P<subfield_label>.*?)\s*(?=.\s*=\s*|\$|\Z)', re.M | re.S)

    search_results = subfield_pattern.finditer(subfields_content)

    for search_result in search_results:
        subfield = Subfield()
        subfield.id = search_result.group('subfield_id').strip().replace('$', '')
        subfield.search_start = search_result.start()
        subfield.search_end = search_result.end()
        subfield_data = search_result.group('subfield_label').strip()

        if subfield_data == 'to':
            continue

        # try to find the last set of parentheses in the subfield data
        # if there are no parentheses, then the subfield data is the label
        # if there are parentheses, then the label is everything before the parentheses

        # first we need to check if there are any parentheses
        parentheses_pattern = re.compile(r'\(.*?\)')
        all_parentheses = parentheses_pattern.findall(subfield_data)

        if len(all_parentheses) == 0:
            subfield.label = subfield_data
        else:
            # now we need to find the last set of parentheses
            last_parentheses: str = all_parentheses[-1]
            subfield.label = subfield_data.replace(last_parentheses, '').strip()

            non_repeatable_pattern = re.compile(r'(Not\s+|Non(\s?|\s*-\s*)?)repeatable', re.IGNORECASE)
            non_repeatable_search_result = non_repeatable_pattern.search(last_parentheses)

            subfield.repeatable = non_repeatable_search_result is None

        subfields.append(subfield)

    # now we get the subfield positions
    subfield_position_pattern = re.compile(r'^\s*(?P<subfield_id>\$.)\s*/\s*(?P<subfield_position>\d{1,2}(-\d{1,2})?)'
                                           r'\s*(?P<position_label>.*?)\s*(?=([\w#]{1,3}\s*=\s*)|\$|\Z)', re.M | re.S)

    search_results = subfield_position_pattern.finditer(subfields_content)

    for search_result in search_results:
        subfield_id = search_result.group('subfield_id').strip().replace('$', '')
        subfield_position = search_result.group('subfield_position').strip()
        position_label = search_result.group('position_label').strip()

        position = Position()
        position.search_start = search_result.start()
        position.search_end = search_result.end()
        position.label = position_label

        if '-' in subfield_position:
            start, end = subfield_position.split('-')
            position.start = int(start)
            position.end = int(end)
        else:
            position.start = int(subfield_position)

        # now we need to find the subfield with this id and assign the position to it
        for s in subfields:
            if s.id == subfield_id:
                s.positions.append(position)

    # we'll have to iterate through all positions of the subfield, and take all the lines between two
    # subfields / subfield positions
    # so we either end with another subfield position, or a subfield, or the end of the content

    # so as a first thing is that we want to iterate through all subfields
    for s_i in range(len(subfields)):
        current_subfield = subfields[s_i]
        next_subfield = subfields[s_i + 1] if s_i < len(subfields) - 1 else None

        for p_i in range(len(current_subfield.positions)):
            current_position = current_subfield.positions[p_i]
            next_position = current_subfield.positions[p_i + 1] if p_i < len(current_subfield.positions) - 1 else None

            # so now make a pattern that's going to get everything from this position to the next position OR to the
            # next subfield in case there isn't a next position OR to the end of the file
            content_start = current_position.search_end
            content_end: Optional[int]
            if next_position is not None:
                content_end = next_position.search_start
            elif next_subfield is not None:
                content_end = next_subfield.search_start
            else:
                content_end = None

            code_content = subfields_content[content_start:content_end] \
                if content_end is not None \
                else subfields_content[content_start:]

            if current_position.end is None:
                codes = get_position_codes(code_content, 1)
            else:
                codes = get_position_codes(code_content, current_position.end - current_position.start + 1)

            current_position.codes = codes

    # return the list of subfields from the dictionary whose values are subfields
    return subfields


def parse(doc: fitz.Document, field_names: [str], next_section_title: Optional[str] = None) -> [UnimarcField]:
    fields: [UnimarcField] = []

    starting_page = 1
    max_pages = 76
    for i in range(len(field_names)):

        field = UnimarcField()

        next_field_name = field_names[i + 1] if i + 1 < len(field_names) else next_section_title
        is_last_field = i == len(field_names) - 1
        field_text, starting_page = get_field_text(field_names[i],
                                                   next_field_name,
                                                   doc,
                                                   starting_page,
                                                   max_pages=max_pages,
                                                   is_last=is_last_field)

        field.name = field_names[i]

        optional, repeatable = get_occurrence(field_names[i], field_text)
        field.optional = optional
        field.repeatable = repeatable

        fields.append(field)

        field.indicators = get_indicators(field_text)

        print('Getting subfields for', field_names[i])
        field.subfields = get_subfields(field_text)

    return fields


# this function saves a list of UnimarcField objects to a json file
def save_to_json_file(file_name, data):
    with open(file_name, 'w') as outfile:
        json.dump(data, outfile, indent=4)


def get_args() -> Tuple[str, bool]:
    parser = argparse.ArgumentParser(description='Parse UNIMARC fields from the UNIMARC concise PDF. '
                                                 'Only works with the 2008 version of the PDF.')
    parser.add_argument('--config', type=str, default='concise-config.json', help='Path to the config file')
    parser.add_argument('--separate', action='store_true', help='Separate the fields into separate files')

    args = parser.parse_args()

    return args.config, args.separate


def open_json(file_path: str) -> dict:
    with open(file_path, 'r') as config_file:
        config = json.load(config_file)
        return config


if __name__ == '__main__':
    config_path, separate = get_args()

    config = open_json(config_path)
    parsed = []
    doc = fitz.Document('unimarc-concise.pdf')
    for field_set in config:
        field_info = config[field_set]
        fields = field_info['fields']
        end_indicator = field_info['endWith']

        fields_parsed = parse(doc, fields, end_indicator)
        if separate:
            save_to_json_file(f'parsed-{field_set}.json', {f.tag: f.to_json() for f in fields_parsed})
        else:
            parsed.extend(fields_parsed)

    if not separate:
        save_to_json_file('parsed.json', {f.tag: f.to_json() for f in parsed})
