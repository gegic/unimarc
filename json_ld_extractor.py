# load json file
# extract json-ld
# save json-ld to file

import json
import re


def load_json_file(file_name):
    with open(file_name) as json_file:
        data = json.load(json_file)
        return data


def extract_field_data(item):
    curie = item['@id'].split('/')[-1]
    tag = curie[1:4]
    indicator1 = curie[4]
    indicator2 = curie[5]
    subfield = curie[6]

    return tag, indicator1, indicator2, subfield


def extract_indicator_labels(subfield, indicator1, indicator2):
    if indicator1 is None and indicator2 is None:
        return

    indicator_data: dict = subfield['indicator_data']
    subfield_label = None
    if indicator1 is not None and indicator2 is not None:
        # extract substrings which are in the two last parentheses sets in subfield label
        # e.g. 'Geographic area code (indicator 1) (indicator 2)'
        for indicator_codes in indicator_data.keys():
            subfield_pattern = re.compile(r'^(?P<subfield_label>[\s\S]+)\((?P<indicator1>.*?)\)\s+\((?P<indicator2>.*?)\)$')
            label = indicator_data[indicator_codes]
            match_result = subfield_pattern.match(label)
            if match_result is not None:
                indicator1_code = indicator_codes[0]
                indicator1['codes'][indicator1_code] = match_result.group('indicator1')
                indicator2_code = indicator_codes[1]
                indicator2['codes'][indicator2_code] = match_result.group('indicator2')
                if subfield_label is not None and subfield_label != match_result.group('subfield_label').strip():
                    raise Exception(f'Subfield label mismatch: {subfield_label} != {match_result.group("subfield_label")}')
                else:
                    subfield_label = match_result.group('subfield_label').strip()
    elif indicator1 is not None:
        # extract substring which is in the last parentheses set in subfield label
        # e.g. 'Geographic area code (indicator 1)'
        for indicator_codes in indicator_data.keys():
            subfield_pattern = re.compile(r'^(?P<subfield_label>[\s\S]+)\((?P<indicator1>.*?)\)$')
            label = indicator_data[indicator_codes]
            match_result = subfield_pattern.match(label)
            if match_result is not None:
                indicator1_code = indicator_codes[0]
                indicator1['codes'][indicator1_code] = match_result.group('indicator1')
                if subfield_label is not None and subfield_label != match_result.group('subfield_label').strip():
                    raise Exception(
                        f'Subfield label mismatch: {subfield_label} != {match_result.group("subfield_label")}')
                else:
                    subfield_label = match_result.group('subfield_label').strip()
    elif indicator2 is not None:
        # extract substring which is in the last parentheses set in subfield label
        # e.g. 'Geographic area code (indicator 2)'
        for indicator_codes in indicator_data.keys():
            subfield_pattern = re.compile(r'^(?P<subfield_label>[\s\S]+)\((?P<indicator2>.*?)\)$')
            label = indicator_data[indicator_codes]
            match_result = subfield_pattern.match(label)
            if match_result is not None:
                indicator2_code = indicator_codes[1]
                indicator2['codes'][indicator2_code] = match_result.group('indicator2')
                if subfield_label is not None and subfield_label != match_result.group('subfield_label').strip():
                    raise Exception(
                        f'Subfield label mismatch: {subfield_label} != {match_result.group("subfield_label")}')
                else:
                    subfield_label = match_result.group('subfield_label').strip()

    subfield['label'] = subfield_label if subfield_label is not None else subfield['label']

def extract_fields(data):
    graph = data['@graph']

    fields = {}

    for item in graph[1:]:
        tag, indicator1, indicator2, subfield = extract_field_data(item)
        if tag not in fields:
            fields[tag] = {
                'indicator1': {
                    'label': '',
                    'codes': {}
                },
                'indicator2': {
                    'label': '',
                    'codes': {}
                },
                'subfields': {}
            }

        field = fields[tag]
        if indicator1 not in field['indicator1']['codes']:
            field['indicator1']['codes'][indicator1] = None
        if indicator2 not in field['indicator2']['codes']:
            field['indicator2']['codes'][indicator2] = None

        if subfield not in field['subfields']:
            field['subfields'][subfield] = {
                'label': '',
                'description': '',
                'indicator_data': {}
            }

        subfield_data = field['subfields'][subfield]
        if 'label' in item and 'en' in item['label']:
            indicator_combination = f'{indicator1}{indicator2}'
            subfield_data['indicator_data'][indicator_combination] = item['label']['en']
            subfield_data['label'] = item['label']['en']

        if 'description' in item and 'en' in item['description']:
            subfield_data['description'] = item['description']['en']

    for tag in fields:
        field = fields[tag]

        indicator1_codes = field['indicator1']['codes'].keys()
        if len(indicator1_codes) == 1 and '_' in indicator1_codes:
            field['indicator1'] = None

        indicator2_codes = field['indicator2']['codes'].keys()
        if len(indicator2_codes) == 1 and '_' in indicator2_codes:
            field['indicator2'] = None

        for subfield in field['subfields']:
            subfield_data = field['subfields'][subfield]
            extract_indicator_labels(subfield_data, field['indicator1'], field['indicator2'])
            del subfield_data['indicator_data']
    return fields



if __name__ == "__main__":
    file_name = 'jsonld.json'
    data = load_json_file(file_name)
    fields = extract_fields(data)

    print(fields)
