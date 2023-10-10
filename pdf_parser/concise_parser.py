# Refining the function to extract fields and subfields information with improved parsing
from typing import Tuple

import fitz
from pdf_parser.models import UnimarcField
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
                   max_pages: int = 580) -> Tuple[str, int]:
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
        field_name_pattern = re.compile(rf'^\s*(?P<field_name>{field_name})\s+\(.*?\)\s*$', re.I | re.M)
        search_result = field_name_pattern.search(page_text)
        if search_result is None and field_text == '':
            continue

        if search_result is not None and field_text == '':
            field_name_start = search_result.start('field_name')
            page_text = page_text[field_name_start:]

        if next_field_name is None:
            field_text += page_text
            continue

        field_text += page_text
        # todo check if the next field name is in the page
        # so what's the problem here apparently
        # we're adding page text to the field text, but we're not checking if the next field name is in the page
        # that means that if the next field name is in the page, we can't remove the rest of the page after the next
        # field name
        next_field_name_pattern = re.compile(rf'^\s+(?P<next_field_name>{next_field_name})\s+\(.*?\)', re.IGNORECASE)
        search_result = next_field_name_pattern.search(page_text)
        if search_result is not None:
            next_field_name_start = search_result.start('next_field_name')
            field_text = field_text[:next_field_name_start]
            break

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
    field_name_pattern = re.compile(rf'^\s*(?P<field_name>{field_name})\s+(\(.*?\))', re.IGNORECASE)
    search_result = field_name_pattern.search(text)
    if search_result is None:
        raise Exception(f'Field {field_name} not found in text')

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


def parse(field_names: [str]):
    doc = fitz.open('unimarc-concise.pdf')
    fields: [UnimarcField] = []

    starting_page = 2
    max_pages = 7
    for i in range(len(field_names)):

        field = UnimarcField()

        next_field_name = field_names[i + 1] if i + 1 < len(field_names) else None
        field_text, starting_page = get_field_text(field_names[i], next_field_name, doc, starting_page,
                                                   max_pages=max_pages)

        field.name = field_names[i]

        optional, repeatable = get_occurrence(field_names[i], field_text)
        field.optional = optional
        field.repeatable = repeatable

        fields.append(field)

    print(fields)
    return fields


if __name__ == '__main__':
    fields_0xx = [
        '001 RECORD IDENTIFIER',
        '003 PERSISTENT RECORD IDENTIFIER',
        '005 VERSION IDENTIFIER',
        '010 INTERNATIONAL STANDARD BOOK NUMBER',
        '011 INTERNATIONAL STANDARD SERIAL NUMBER',
        '012 FINGERPRINT IDENTIFIER',
        '013 INTERNATIONAL STANDARD MUSIC NUMBER',
        '014 ARTICLE IDENTIFIER',
        '015 INTERNATIONAL STANDARD TECHNICAL REPORT NUMBER',
        '016 INTERNATIONAL STANDARD RECORDING CODE (ISRC)',
        '017 OTHER STANDARD IDENTIFIER',
        '020 NATIONAL BIBLIOGRAPHY NUMBER',
        '021 LEGAL DEPOSIT NUMBER',
        '022 GOVERNMENT PUBLICATION NUMBER',
        '035 OTHER SYSTEM CONTROL NUMBERS',
        '036 MUSIC INCIPIT',
        '040 CODEN (SERIALS)',
        '071 PUBLISHER\'S NUMBER',
        '072 UNIVERSAL PRODUCT CODE (UPC)',
        '073 INTERNATIONAL ARTICLE NUMBER (EAN)'
    ]

    fields_1xx = [
        '100 GENERAL PROCESSING DATA',
        '101 LANGUAGE OF THE ITEM',
        '102 Country of Publication or Production',
        '105 Coded Data Field: Textual language material, Monographic',
        '106 Coded Data Field: Form of item',
        '110 Coded Data Field: Continuing Resources',
        '111 Coded Data Field - Serials: Physical Attributes - [Obsolete]',
        '115 Coded Data Fields: Visual Projections, Videorecordings and Motion Pictures',
        '116 Coded Data Field: Graphics',
        '117 Coded Data Field: Three-dimensional artefacts and realia',
        '120 Coded Data Field: Cartographic Materials - General',
        '121 Coded Data Field: Cartographic Materials: Physical Attributes',
        '122 Coded Data Field: Time Period of Item Content',
        '123 Coded Data Field: Cartographic Materials - Scale and Co-ordinates',
        '124 Coded Data Field: Cartographic Materials - Specific Material Designation Analysis',
        '125 Coded Data Field: Sound Recordings and Music',
        '126 Coded Data Field: Sound Recordings - Physical Attributes',
        '127 Coded Data Field: Duration of Sound Recordings and Printed Music',
        '128 Coded Data Field: Form of Musical Work and Key or Mode',
        '130 Coded Data Field: Microforms - Physical attributes',
        '131 Coded Data Field: Cartographic Materials: Geodetic, Grid and Vertical Measurement',
        '135 Coded Data Field: Electronic resources',
        '140 Coded Data Field: Antiquarian - General',
        '141 Coded Data Field -- Copy Specific Attributes',
        '145 Coded Data Field: Medium of Performance',
    ]

    parse(fields_0xx)