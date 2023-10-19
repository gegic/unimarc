import json
import re

import requests as requests


def load_json_file(file_name):
    with open(file_name) as json_file:
        data = json.load(json_file)
        return data


def save_to_json_file(file_name, data):
    with open(file_name, 'w') as outfile:
        json.dump(data, outfile, indent=4)


def extract_field_data(item):
    """
    Extracts the field data from the item's @id field

    Example:
        http://iflastandards.info/ns/unimarc/unimarcb/elements/0XX/U0110_a ->
        tag: 011, indicator1: 0, indicator2: None, subfield: a
    :param item: An instance of subfield used together with indicators.
    :return: A quadruple containing the tag, indicator1, indicator2 and subfield.
    """
    curie = item['@id'].split('/')[-1]

    if len(curie) > 7:
        # still not handling positions
        return None

    if len(curie) == 5:
        tag = curie[1:4]
        indicator1 = None
        indicator2 = None
        subfield = curie[4]
        return tag, indicator1, indicator2, subfield

    tag = curie[1:4]
    indicator1 = curie[4]
    indicator2 = curie[5]
    subfield = curie[6]

    return tag, indicator1, indicator2, subfield


def extract_content_within_parentheses(s, pos):
    if pos < 0:
        pos += len(s)

    stack = []
    for i, c in enumerate(s[:pos+1]):
        if c == '(':
            stack.append(i)
        elif c == ')':
            if i != pos:  # Skip popping for the closing parenthesis at the given position
                stack.pop()

    if not stack:
        return None

    opening_pos = stack[-1]

    # Extract the content within the parentheses, accounting for the end character
    content = s[opening_pos+1:pos]
    return content


def process_indicator(indicator_data, indicator, indicator_index) -> str:
    """
    Extracts the content from within the last parenthesis set.
    :param indicator_data: A dictionary where indicator codes map to common labels.
        Meaning *0_* can map to 'Some subfield label (indicator1 label)'.
    :param indicator: Current indicator which the label and the code is being assigned to.
    :param indicator_index: The index of the indicator. Used to get the indicator label from the match result.
    :return: The subfield label without this indicator's label.
    """

    for indicator_codes in indicator_data.keys():
        common_label = indicator_data[indicator_codes]

        result_indicator_label = extract_content_within_parentheses(common_label, -1)
        indicator_code = indicator_codes[indicator_index]

        if indicator['codes'].get(indicator_code) is None:
            indicator['codes'][indicator_code] = list()

        if result_indicator_label not in indicator['codes'][indicator_code]:
            indicator['codes'][indicator_code].append(result_indicator_label)

        indicator_data[indicator_codes] = common_label.replace(f'({result_indicator_label})', '').strip()


def extract_indicator_codes(subfield, indicator1, indicator2):
    """
    Extracts all indicator codes given one subfield. It would be sufficient to extract the indicator codes
    from only one subfield, but this method is used to check if the indicator codes are the same for all subfields and
    if the subfield label is the same for all indicators. If the subfield label is not the same for all indicators,
    an exception is raised.
    :param subfield:
    :param indicator1:
    :param indicator2:
    :return:
    """
    if indicator1 is None and indicator2 is None:
        return

    indicator_data: dict = subfield['indicator_data']
    subfield_label = None
    if indicator1 is not None and indicator2 is not None:
        process_indicator(indicator_data, indicator1, 0)
        process_indicator(indicator_data, indicator2, 1)
    elif indicator1 is not None:
        process_indicator(indicator_data, indicator1, 0)
    elif indicator2 is not None:
        process_indicator(indicator_data, indicator2, 1)

    # make sure that all the values from indicator_data are identical
    for common_label in indicator_data.values():
        if subfield_label is None:
            subfield_label = common_label
        elif subfield_label != common_label:
            raise Exception(f'Subfield {subfield} has different labels for indicators')

    subfield['label'] = subfield_label if subfield_label is not None else subfield['label']


def get_field(fields, tag):
    """
    Gets the field from the fields dictionary. If the field for the given tag does not exist, it is created.
    :param fields:
    :param tag:
    :return:
    """
    if tag not in fields:
        fields[tag] = {
            'indicator1': {'label': '', 'codes': {}},
            'indicator2': {'label': '', 'codes': {}},
            'subfields': {}
        }
    return fields[tag]


def update_subfield(field, indicator1, indicator2, subfield, item):
    """
    Updates the subfield data with the given parameters. Also, creates the indicator data if it does not exist.
    :param field:
    :param indicator1:
    :param indicator2:
    :param subfield:
    :param item:
    :return:
    """
    subfield_data = field['subfields'].setdefault(subfield, {
        'label': '',
        'description': '',
        'indicator_data': {}
    })

    indicator_combination = f'{indicator1}{indicator2}'
    subfield_data['indicator_data'][indicator_combination] = item.get('label', {}).get('en', '')
    subfield_data['label'] = item.get('label', {}).get('en', '')
    subfield_data['description'] = item.get('description', {}).get('en', [''])[0]


def set_indicators(field, indicator1, indicator2):
    """
    Sets the indicators for the given field. If the indicators already exist, they are not overwritten.
    :param field:
    :param indicator1:
    :param indicator2:
    :return:
    """
    field['indicator1']['codes'].setdefault(indicator1, None)
    field['indicator2']['codes'].setdefault(indicator2, None)


def clean_fields(fields):
    """
    Removes the indicator1 and indicator2 if they only have one code and that code is '_'. Also, removes the list
    from the indicator codes if the length of the list is 1.

    Additionally, populates codes for indicators using the indicator_data from subfields.
    :param fields:
    :return:
    """
    for tag, field in fields.items():
        indicator1_codes = field['indicator1']['codes'].keys()
        indicator2_codes = field['indicator2']['codes'].keys()

        if len(indicator1_codes) == 1 and '_' in indicator1_codes:
            field['indicator1'] = None

        if len(indicator2_codes) == 1 and '_' in indicator2_codes:
            field['indicator2'] = None

        for subfield, subfield_data in field['subfields'].items():
            extract_indicator_codes(subfield_data, field['indicator1'], field['indicator2'])
            del subfield_data['indicator_data']

        # iterate through all iterator codes, and if length of their labels is 1, then remove the list and
        # just keep the string
        if field['indicator1'] is not None:
            for indicator_code, indicator_label in field['indicator1']['codes'].items():
                if len(indicator_label) == 1:
                    field['indicator1']['codes'][indicator_code] = indicator_label[0]
        if field['indicator2'] is not None:
            for indicator_code, indicator_label in field['indicator2']['codes'].items():
                if len(indicator_label) == 1:
                    field['indicator2']['codes'][indicator_code] = indicator_label[0]


def extract_fields(data):
    graph = data['@graph']

    fields = {}
    for item in graph[1:]:
        field_data = extract_field_data(item)
        if field_data is None:
            continue
        tag, indicator1, indicator2, subfield = field_data
        field = get_field(fields, tag)

        set_indicators(field, indicator1, indicator2)
        update_subfield(field, indicator1, indicator2, subfield, item)

    clean_fields(fields)

    return fields


if __name__ == "__main__":

    sets = [
        '0XX',
        '1XX',
        '2XX',
        '3XX',
        '41X',
        '42X',
        '43X',
        '44X',
        '45X',
        '46X',
        '47X',
        '48X',
        # '5XX', absolutely useless for now due to low quality of data
        '60X',
        '61X',
        '62X',
        '66X',
        '67X',
        '68X',
        '7XX',
        '801',
        '802',
        '830',
        '850',
        '856',
        '886'
    ]

    for element_set in sets:
        print(f'Processing {element_set}')
        url = f'http://iflastandards.info/ns/unimarc/unimarcb/elements/{element_set}.jsonld'
        data = requests.get(url).json()
        fields = extract_fields(data)
        save_to_json_file(f'{element_set}.json', fields)
