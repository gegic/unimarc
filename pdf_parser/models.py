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