from typing import Optional
import fitz
import re

HEADER_FOOTER_PATTERN = re.compile(r'^(UNIMARC\sManual\s+[\w\-]{3}|[\w\-]{3}\s+UNIMARC\sManual)\s+'
                                   r'(UNIMARC\sBibliographic,\s3rd\sedition\s+\d{4}'
                                        r'|\d{4}\s+UNIMARC\sBibliographic,\s3rd\sedition)\s+'
                                   r'\d{2,3}')


class UnimarcField:
    def __init__(self):
        self.name = None
        self.definition = None
        self.optional = None
        self.repeatable = None
        self.indicators = None

    def __str__(self):
        return f'{self.name}\n{self.definition}\n{self.optional}\n{self.repeatable}'

    def __repr__(self):
        return f'\n{self.name}:\n{self.definition}\n{"Optional" if self.optional else "Mandatory"}\n{"Repeatable" if self.repeatable else "Not repeatable"}'


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


class Code:
    def __init__(self):
        self.id = None
        self.label = None

    def __str__(self):
        return f'{self.id} - {self.label}'

    def __repr__(self):
        return f'{self.id} - {self.label}'


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
    blank_pattern = re.compile(r'(blank|no\sindicator|no\sindicators|not\sapplicable|'
                               r'not\sapplicable\sfor\sfield|not\sdefined|undefined)', re.I | re.M)
    search_result = blank_pattern.search(indicator)
    return search_result is not None


def get_indicator_codes(indicator_code_content: str) -> Optional[list]:
    """
    Gets indicator codes from indicator
    :param indicator_code_content:
    :return:
    """
    indicator_code_content = indicator_code_content.strip()
    indicator_codes = []

    code_content_lines = indicator_code_content.splitlines()

    for line in code_content_lines:
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
    if search_result is None:
        indicator_pattern = re.compile(r'^(?P<description>[\s\S]+)\s+0[\s\S]+$', re.M)
        search_result = indicator_pattern.search(indicator_content)
        if search_result is None:
            return None

    indicator_data.description = search_result.group('description')

    indicator_code_content = indicator_content.replace(indicator_data.description, '', 1).strip()
    indicator_data.codes = get_indicator_codes(indicator_code_content)

    return indicator_data


def get_indicators(text: str) -> Optional[list]:
    indicator_list: [Indicator] = []

    indicators_pattern = re.compile(r'^Indicators\s+([\s\S]+)Subfields', re.M)
    search_result = indicators_pattern.search(text)
    if search_result is None:
        # in this case, there's probably something wrong with parsing
        return None

    indicators = search_result.group(1)

    no_indicator_pattern = re.compile(r'(no\sindicators?|not\shave\sindicators|doesn.?t\shave\sindicators)', re.I | re.M)
    search_result = no_indicator_pattern.search(indicators)
    if search_result is not None:
        return None

    # look for Indicator 1
    indicator_1_pattern = re.compile(r'Indicator\s([1lIi]):(?P<indicator1>[\s\S]+)Indicator\s(2|II|Z|z):', re.M)
    search_result = indicator_1_pattern.search(indicators)

    if search_result is None:
        # this shouldn't happen now
        return None

    indicator_content_1 = search_result.group('indicator1')
    if check_blank_indicator(indicator_content_1):
        indicator_list.append(None)
    else:
        indicator_1 = get_indicator_data(indicator_content_1)
        indicator_list.append(indicator_1)

    indicator_2_pattern = re.compile(r'Indicator\s(2|II|Z|z):(?P<indicator2>[\s\S]+)$', re.M)
    search_result = indicator_2_pattern.search(indicators)

    if search_result is None:
        # this shouldn't happen now
        return None

    indicator_content_2 = search_result.group('indicator2')
    if check_blank_indicator(indicator_content_2):
        indicator_list.append(None)
    else:
        indicator_2 = get_indicator_data(indicator_content_2)
        indicator_list.append(indicator_2)

    return indicator_list


def main(field_names: [str]):
    doc = fitz.open('unimarc-b.pdf')
    fields: [UnimarcField] = []

    field = UnimarcField()
    field_text = ''
    for i in range(32, 600):
        if len(field_names) == 0:
            break

        page = doc[i].get_text()
        first_rows = HEADER_FOOTER_PATTERN.search(page)

        if first_rows is None or first_rows.group(0) is None:
            raise Exception(f'Page {i} not supported')

        page = page.replace(first_rows.group(0), '', 1)
        field_text += page

        # if the page contains field name, check this page
        field.name = field_names[0]
        field_name = (re.sub(r'\s+', ' ', field.name)
                      .replace(' ', '\\s+')
                      .replace('(', '\\(')
                      .replace(')', '\\)'))

        field_name_pattern = re.compile(rf'^\s+({field_name})', re.IGNORECASE)

        search_result = field_name_pattern.search(page)
        if search_result is None:
            continue

        field_names.pop(0)

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

        field_text = ''
        field = UnimarcField()

    for field in fields:
        print(field.name, field.indicators)


if __name__ == '__main__':
    names = [
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

    first_page = 33
    last_page = 100

    main(names)
