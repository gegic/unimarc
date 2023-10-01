from typing import Optional, Tuple, Union, List
import fitz
import re
import json

HEADER_FOOTER_PATTERN = re.compile(r'^(UNIMARC\sManual\s+[\w\-]{3}|[\w\-]{3}\s+UNIMARC\sManual)\s+'
                                   r'(UNIMARC\sBibliographic,\s3rd\sedition\s+\d{4}'
                                   r'|\d{4}\s+UNIMARC\sBibliographic,\s3rd\sedition)\s+'
                                   r'\d{2,3}', re.I)


# this function saves a list of UnimarcField objects to a json file
def save_to_json_file(file_name, data):
    with open(file_name, 'w') as outfile:
        json.dump(data, outfile, indent=4)


class UnimarcField:
    def __init__(self):
        self.name = None
        self.definition = None
        self.optional = None
        self.repeatable = None
        self.indicators = None
        self.subfields = None

    def __str__(self):
        return f'{self.name}\n{self.definition}\n{self.optional}\n{self.repeatable}'

    def __repr__(self):
        return f'\n{self.name}:\n{self.definition}\n{"Optional" if self.optional else "Mandatory"}\n{"Repeatable" if self.repeatable else "Not repeatable"}'

    def to_json(self):
        return {
            'tag': self.name[:3],
            'label': self.name[4:],
            'definition': self.definition,
            'optional': self.optional,
            'repeatable': self.repeatable,
            'indicator1': self.indicators[0].to_json() if self.indicators is not None
                                                          and self.indicators[0] is not None else None,
            'indicator2': self.indicators[1].to_json() if self.indicators is not None
                                                          and self.indicators[1] is not None else None,
            'subfields': {
                s.id: s.to_json() for s in filter(lambda x: x is not None, self.subfields)
            } if self.subfields is not None else None
        }


class Indicator:
    """
    Represents indicator with all its options
    """

    def __init__(self):
        self.label = None
        self.description = None
        self.codes = None

    def __str__(self):
        return f'{self.label}: {self.description}'

    def __repr__(self):
        return f'\n{self.label}: {self.description}\n{self.codes}'

    def to_json(self):
        return {
            'label': self.label,
            'description': self.description,
            'codes': {c.id: c.label for c in self.codes}
        }


class Code:
    def __init__(self):
        self.id = None
        self.label = None

    def __str__(self):
        return f'{self.id} - {self.label}'

    def __repr__(self):
        return f'{self.id} - {self.label}'


class Position:
    def __init__(self):
        self.start = None
        self.end = None
        self.codes = None

    def __str__(self):
        return f'{self.start} - {self.end}'

    def __repr__(self):
        return f'{self.start} - {self.end}: {self.codes}'

    def to_json(self):
        return {
            'start': self.start,
            'end': self.end,
            'codes': [c.to_json() for c in self.codes]
        }


class Subfield:
    def __init__(self):
        self.id = None
        self.label = None
        self.description = None
        self.repeatable = None
        self.positions = None

    def __str__(self):
        return f'{self.id} - {self.label}'

    def __repr__(self):
        return f'{self.id} - {self.label}: {self.description}'

    def to_json(self):
        return {
            'label': self.label,
            'description': self.description,
            'repeatable': self.repeatable,
            'positions': [p.to_json() for p in self.positions] if self.positions is not None else None
        }


def get_occurrence(text: str) -> (bool, bool):
    """
    Gets occurrence of the field
    :param text:
    :return: (optional, repeatable)
    """
    occurrence_pattern = re.compile(r'^Occurrence\s+([\s\S]+)Indicators', re.M)
    search_result = occurrence_pattern.search(text)
    if search_result is None:
        # print('NOT WORKING')
        return None

    occurrence = search_result.group(1)

    mandatory_pattern = re.compile(r'(Mandatory|Not optional|Non-?optional)', re.I | re.M)
    search_result = mandatory_pattern.search(occurrence)
    optional = search_result is None

    repeatable_pattern = re.compile(r'(Non-?repeatable|Not repeatable)', re.I | re.M)
    search_result = repeatable_pattern.search(occurrence)
    repeatable = search_result is None
    return optional, repeatable


def check_blank_indicator(indicator: str) -> bool:
    """
    Checks if the indicator is blank
    :param indicator:
    :return:
    """
    blank_pattern = re.compile(r'(blank|not\sdefined)', re.I | re.M)
    search_result = blank_pattern.search(indicator)
    return search_result is not None


def reformat_indicator_code_content(indicator_code_content: str) -> str:
    """
    Reformat indicator code content to be able to parse it
    :param indicator_code_content:
    :return:
    """
    indicator_code_content = indicator_code_content.strip()
    # if the content is in the form '1 \nSome text\n2 \nOther text\n3 \nThird text'
    # we need to reformat it to '1 Some text\n2 Other text\n3 Third text'

    # remove all newlines between numbers and text. hope this will work
    indicator_code_content = re.sub(r'(\d|#)\s*\n\s*(\w)', r'\1 \2', indicator_code_content)

    return indicator_code_content


def get_indicator_codes(indicator_code_content: str) -> Optional[list]:
    """
    Gets indicator codes from indicator.
    :param indicator_code_content:
    :return:
    """
    indicator_code_content = indicator_code_content.strip()
    indicator_codes = []

    indicator_code_content = reformat_indicator_code_content(indicator_code_content)
    code_content_lines = indicator_code_content.splitlines()

    # simply try to get the codes by line and ignore everything else
    for line in code_content_lines:
        line = line.strip()
        if not line[0].isnumeric() and line[0] != '#':
            continue
        code = Code()
        code.id = line[:1]
        code.label = line[1:].strip()
        indicator_codes.append(code)

    return indicator_codes


def get_indicator_data(indicator_content: str) -> Optional[Indicator]:
    """
    Gets data from indicator
    :param indicator_content:
    :return:
    """
    indicator_content = indicator_content.strip()
    indicator_data = Indicator()

    indicator_data.label = indicator_content.splitlines()[0].strip()
    indicator_content = indicator_content.replace(indicator_data.label, '', 1).strip()

    indicator_pattern = re.compile(r'^(?P<description>[\s\S]+)\s+#[\s\S]+$', re.M)
    search_result = indicator_pattern.search(indicator_content)
    if search_result is not None:
        indicator_data.description = search_result.group('description')
    else:
        indicator_pattern = re.compile(r'^(?P<description>[\s\S]+)\s+0[\s\S]+$', re.M)
        search_result = indicator_pattern.search(indicator_content)
        if search_result is not None:
            indicator_data.description = search_result.group('description')

    if indicator_data.description is not None:
        indicator_content = indicator_content.replace(indicator_data.description, '', 1).strip()
    indicator_data.codes = get_indicator_codes(indicator_content)

    return indicator_data


def get_indicators(text: str) -> Tuple[Optional[Indicator], Optional[Indicator]]:
    indicator_list: [Indicator] = []

    indicators_pattern = re.compile(r'^Indicators\s+([\s\S]+)Subfields', re.M)
    search_result = indicators_pattern.search(text)
    if search_result is None:
        # in this case, there's probably something wrong with parsing
        return None, None

    indicators = search_result.group(1)

    no_indicator_pattern = re.compile(r'(no\sindicators?|not\shave\sindicators|doesn.?t\shave\sindicators)',
                                      re.I | re.M)
    search_result = no_indicator_pattern.search(indicators)
    if search_result is not None:
        return None

    # look for Indicator 1
    indicator_1_pattern = re.compile(r'Indicator\s([1lIi]):(?P<indicator0>[\s\S]+)Indicator\s(2|II|Z|z):', re.M)
    search_result = indicator_1_pattern.search(indicators)

    if search_result is None:
        # this shouldn't happen now
        return None, None

    indicator_content_1 = search_result.group('indicator0')
    if check_blank_indicator(indicator_content_1):
        indicator_list.append(None)
    else:
        indicator_1 = get_indicator_data(indicator_content_1)
        indicator_list.append(indicator_1)

    indicator_2_pattern = re.compile(r'Indicator\s(2|II|Z|z):(?P<indicator1>[\s\S]+)$', re.M)
    search_result = indicator_2_pattern.search(indicators)

    if search_result is None:
        # this shouldn't happen now
        return None, None

    indicator_content_2 = search_result.group('indicator1')
    if check_blank_indicator(indicator_content_2):
        indicator_list.append(None)
    else:
        indicator_2 = get_indicator_data(indicator_content_2)
        indicator_list.append(indicator_2)

    return indicator_list


def get_subfields(text: str) -> Optional[list]:
    subfields: [Subfield] = []

    subfield_section_pattern = re.compile(r'^\s*Subfields\s+([\s\S]+)^\s*Notes?\s*on\s*(sub)?field\s*contents?',
                                          re.I | re.M)

    search_result = subfield_section_pattern.search(text)
    if search_result is None:
        return None

    subfields_content = search_result.group(1)

    subfield_pattern = re.compile(r'^\s*(?P<label>\$\w)\s+(?P<name>[^\n]+)$', re.M)
    search_results = subfield_pattern.findall(subfields_content)

    for search_result in search_results:
        subfield = Subfield()
        subfield.id = search_result[0].strip()
        subfield.label = search_result[1].strip()
        # subfield.description = search_result[2].strip()
        subfields.append(subfield)

    # now get the description for each subfield which is inbetween the subfield name and the next subfield name
    # this is to make sure that we don't miss the entire description in case some subfield $x is mentioned in the
    # description

    for i in range(len(subfields)):
        subfield = subfields[i]
        if i + 1 < len(subfields):
            next_subfield = subfields[i + 1]
        else:
            next_subfield = None

        subfield_mention_1 = form_regex_pattern(f'{subfield.id} {subfield.label}')
        subfield_mention_2 = None

        if next_subfield is not None:
            subfield_mention_2 = form_regex_pattern(f'{next_subfield.id} {next_subfield.label}')

        subfield_description_pattern = re.compile(
            rf'\s*({subfield_mention_1})\s+(?P<description>[\s\S]+?)\s*({subfield_mention_2 if next_subfield is not None else "$"})')
        search_result = subfield_description_pattern.search(subfields_content)
        if search_result is not None:
            subfield.description = search_result.group('description').strip()
    return subfields


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
        first_rows = HEADER_FOOTER_PATTERN.search(page_text)
        if first_rows is None or first_rows.group(0) is None:
            raise Exception(f'Page {i} not supported')

        page_text = page_text.replace(first_rows.group(0), '', 1)

        # if the page contains field name, check this page
        field_name_pattern = re.compile(rf'^\s*({field_name})', re.IGNORECASE)
        search_result = field_name_pattern.search(page_text)
        if search_result is None and field_text == '':
            continue

        if next_field_name is None:
            field_text += page_text
            continue

        next_field_name_pattern = re.compile(rf'^\s+({next_field_name})', re.IGNORECASE)
        search_result = next_field_name_pattern.search(page_text)
        if search_result is not None:
            break

        field_text += page_text

    # print('Found', field_name, 'ending on page', i)

    return field_text, i


def parse(field_names: [str]):
    doc = fitz.open('pdf_parser/unimarc-b.pdf')
    fields: [UnimarcField] = []

    starting_page = 32
    max_pages = 82
    for i in range(len(field_names)):

        field = UnimarcField()

        next_field_name = field_names[i + 1] if i + 1 < len(field_names) else None
        field_text, starting_page = get_field_text(field_names[i], next_field_name, doc, starting_page,
                                                   max_pages=max_pages)

        field.name = field_names[i]
        # FIELD DEFINITION PART
        field_definition_pattern = re.compile(r'^Field [Dd]efinition\s+([\s\S]+)Occurrence', re.M)
        search_result = field_definition_pattern.search(field_text)

        if search_result is None:
            # print('!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!')
            # print(field_name)
            # print(i)
            # sr = re.compile(r'Field Definition\s+([\s\S]+)', re.M).search(text)
            # if sr is not None:
            #     print(sr.group())
            continue

        field_definition = search_result.group(1)
        field.definition = field_definition

        # OCCURRENCE
        optional, repeatable = get_occurrence(field_text)
        field.optional = optional
        field.repeatable = repeatable

        fields.append(field)

        # INDICATORS
        indicators = get_indicators(field_text)
        field.indicators = indicators

        # SUBFIELDS
        subfields = get_subfields(field_text)
        field.subfields = subfields

    return fields


if __name__ == '__main__':
    fields_0xx = [
        '001 Record Identifier',
        '003 Persistent Record Identifier',
        '005 Version Identifier',
        '010 International Standard Book Number',
        '011 ISSN',
        '012 Fingerprint Identifier',
        '013 International Standard Music Number (ISMN)',
        '014 Article Identifier',
        '015 International Standard Technical Report Number (ISRN)',
        '016 International Standard Recording Code (ISRC)',
        '017 Other Standard Identifier',
        '020 National Bibliography Number',
        '021 Legal Deposit Number',
        '022 Government Publication Number',
        '035 Other System Control Numbers',
        '036 Music Incipit',
        '040 CODEN',
        '071 Publisher\'s Number',
        '072 Universal Product Code (UPC)',
        '073 International Article Number (EAN)'
    ]

    fields_1xx = [
        '100 General Processing Data',
        '101 Language of the Item',
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

    fields = parse(fields_0xx)
    field_list = [f.to_json() for f in fields]
    save_to_json_file('pdf_parser/fields.json', field_list)
