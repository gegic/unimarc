import json
import re


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
    tag = curie[1:4]
    indicator1 = curie[4]
    indicator2 = curie[5]
    subfield = curie[6]

    return tag, indicator1, indicator2, subfield


def process_indicator(indicator_data, indicator, indicator_index, current_subfield_label, pattern):
    """
    Extracts the indicator label from the common label associated with indicator_codes.
    :param indicator_data: A dictionary where indicator codes map to common labels.
        Meaning *0_* can map to 'Some subfield label (indicator1 label)'.
    :param indicator: Current indicator which the label and the code is being assigned to.
    :param indicator_index: The index of the indicator. 0 for indicator1 and 1 for indicator2.
    :param current_subfield_label: The subfield label extracted from the common label. Used to check if
        the subfield label is the same for all indicators.
    :param pattern: The pattern used to extract the indicator labels as well as the subfield label
        from the common label.
    :return:
    """
    for indicator_codes in indicator_data.keys():
        subfield_pattern = re.compile(pattern)
        common_label = indicator_data[indicator_codes]
        match_result = subfield_pattern.match(common_label)
        if match_result is not None:
            indicator_code = indicator_codes[indicator_index]
            result_indicator_label = match_result.group(f'indicator{indicator_index + 1}')
            # Originally the idea was to raise an exception if the indicator label is not the same for all
            # subfields. However, it turns out that there are some cases where the indicator label is not the same
            # probably due to errors in the data.

            # current_indicator_label = indicator['codes'][indicator_code]
            # if current_indicator_label is not None and current_indicator_label != result_indicator_label:
            # So, instead of raising an exception, we add this element to the set

            if indicator['codes'].get(indicator_code) is None:
                indicator['codes'][indicator_code] = list()

            if result_indicator_label not in indicator['codes'][indicator_code]:
                indicator['codes'][indicator_code].append(result_indicator_label)

            result_subfield_label = match_result.group('subfield_label').strip()
            if current_subfield_label is not None and current_subfield_label != result_subfield_label:
                raise Exception(f'Subfield label mismatch: {current_subfield_label} != {result_subfield_label}')
            else:
                current_subfield_label = result_subfield_label


def extract_indicator_labels(subfield, indicator1, indicator2):
    """
    Extracts all indicator labels given one subfield. It would be sufficient to extract the indicator labels
    from only one subfield, but this method is used to check if the indicator labels are the same for all subfields and
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
        pattern = r'^(?P<subfield_label>[\s\S]+)\((?P<indicator1>.*?)\)\s+\((?P<indicator2>.*?)\)$'
        process_indicator(indicator_data, indicator1, 0, subfield_label, pattern)
        process_indicator(indicator_data, indicator2, 1, subfield_label, pattern)

    elif indicator1 is not None:
        pattern = r'^(?P<subfield_label>[\s\S]+)\((?P<indicator1>.*?)\)$'
        process_indicator(indicator_data, indicator1, 0, subfield_label, pattern)

    elif indicator2 is not None:
        pattern = r'^(?P<subfield_label>[\s\S]+)\((?P<indicator2>.*?)\)$'
        process_indicator(indicator_data, indicator2, 1, subfield_label, pattern)

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
            extract_indicator_labels(subfield_data, field['indicator1'], field['indicator2'])
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
        tag, indicator1, indicator2, subfield = extract_field_data(item)
        field = get_field(fields, tag)

        set_indicators(field, indicator1, indicator2)
        update_subfield(field, indicator1, indicator2, subfield, item)

    clean_fields(fields)

    return fields


if __name__ == "__main__":
    file_name = 'json_ld/jsonld.json'
    data = load_json_file(file_name)
    fields = extract_fields(data)
    save_to_json_file('json_ld/fields.json', fields)
