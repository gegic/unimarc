import json


def open_json_file(file_name):
    with open(file_name) as json_file:
        data = json.load(json_file)
        return data


def check_indicator(indicator_name, jsonld_field, pdf_field, should_check_labels=True, verbose=True):
    # check that the indicators are the same
    # meaning: either both are null, or both have the same labels and codes

    jsonld_indicator = jsonld_field[indicator_name]
    pdf_indicator = pdf_field[indicator_name]

    if jsonld_indicator is not None and pdf_indicator is None:
        print('Tag {} has indicator1 in jsonld but not in pdf_fields'.format(tag))
        return

    if jsonld_indicator is None and pdf_indicator is not None:
        print('Tag {} has indicator1 in pdf_fields but not in jsonld'.format(tag))
        return

    if jsonld_indicator is None and pdf_indicator is None:
        return


    if should_check_labels:
        # check that the labels are the same
        jsonld_label = jsonld_indicator['label']
        pdf_label = pdf_indicator['label']

        if jsonld_label != pdf_label:
            print(f'Tag {tag} has different labels for {indicator_name}')
            print(f'jsonld label: {jsonld_label}')
            print(f'pdf label: {pdf_label}')

    # check that the codes are the same
    # codes are a dictionary of code: label
    jsonld_codes = jsonld_indicator['codes']
    pdf_codes = pdf_indicator['codes']

    if verbose:
        # print both codes nicely
        print('jsonld codes:')
        print(jsonld_codes)
        print('pdf codes:')
        print(pdf_codes)

    if len(jsonld_codes) != len(pdf_codes):
        print(f'Tag {tag} has different number of codes for {indicator_name}')
        return

    # check that the codes are the same
    for code, label in jsonld_codes.items():
        if code not in pdf_codes:
            print(f'Indicator: Tag {tag} has code {code} in jsonld but not in pdf_fields')
            return

        if not should_check_labels:
            continue

        # make sure that both labels we're checking have no \n, \r and that they are lowercase
        label = label.replace('\n', '').replace('\r', '').lower()
        pdf_label = pdf_codes[code].replace('\n', '').replace('\r', '').lower()

        if label != pdf_label:
            print(f'Tag {tag} has different labels for code {code} in {indicator_name}')
            print(f'jsonld label: {label}')
            print(f'pdf label: {pdf_codes[code]}')
            return


def check_subfields(jsonld_field, pdf_field, should_check_labels=True, verbose=True):
    # check that the subfields are the same
    jsonld_subfields = jsonld_field['subfields']
    pdf_subfields = pdf_field['subfields']

    if verbose:
        # print both subfields nicely
        print('jsonld subfields:')
        print(jsonld_subfields)

        print('pdf subfields:')
        print(pdf_subfields)

    # check if any is none while other is not
    if jsonld_subfields is None and pdf_subfields is not None:
        print(f'Tag {tag} has subfields in pdf_fields but not in jsonld')
        return

    if jsonld_subfields is not None and pdf_subfields is None:
        print(f'Tag {tag} has subfields in jsonld but not in pdf_fields')
        return

    if jsonld_subfields is None and pdf_subfields is None:
        return

    if len(jsonld_subfields) != len(pdf_subfields):
        print(f'Tag {tag} has different number of subfields')
        return

    # now for each jsonld_subfield, check that it is in pdf_subfields
    for subfield, subfield_data in jsonld_subfields.items():
        if subfield not in pdf_subfields:
            print(f'Subfield {subfield} not found in pdf_fields field {tag}')
            continue

        # check that labels of subfield_data are the same as pdf_subfields
        if not should_check_labels:
            continue

        jsonld_subfield_label = subfield_data['label']
        pdf_subfield_label = pdf_subfields[subfield]['label']

        # make sure to remove and \n or \r from the labels and to make them lowercase
        jsonld_subfield_label = jsonld_subfield_label.replace('\n', '').replace('\r', '').lower()
        pdf_subfield_label = pdf_subfield_label.replace('\n', '').replace('\r', '').lower()

        if jsonld_subfield_label != pdf_subfield_label:
            print(f'Subfield {subfield} has different labels: {tag}')
            print(f'jsonld label: {jsonld_subfield_label}')
            print(f'pdf label: {pdf_subfield_label}')
            continue


jsonld_fields = open_json_file('json_ld/5XX.json')
pdf_fields = open_json_file('pdf_parser/parsed-5xx.json')

# make sure that every field in json_ld_fields can be found in pdf_fields
for tag, field in jsonld_fields.items():
    # find the item with the same tag in pdf_fields list
    pdf_field = None
    for pdf_field_tag in pdf_fields:
        if pdf_field_tag == tag:
            pdf_field = pdf_fields[pdf_field_tag]
            break

    if pdf_field is None:
        print('Tag {} not found in pdf_fields'.format(tag))
        continue

    # check that the indicators are the same
    check_indicator('indicator1', field, pdf_field, False, False)
    check_indicator('indicator2', field, pdf_field, False, False)

    check_subfields(field, pdf_field, False, False)
