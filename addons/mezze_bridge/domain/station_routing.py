# -*- coding: utf-8 -*-
"""Which prep station a product belongs to — the rule, with no ORM.

Extracted because two places now need it: the controller that builds kitchen
tickets live, and the outbox consumer that prints one after the fact. A routing
rule copied into both is a rule that will disagree with itself the first time
somebody adds a keyword to one copy — and the symptom would be a ticket printing
at the pass while the kitchen display shows it at the bar.

Real deployments would drive this off a category-to-station table; the keyword
matching below is the shipped default and is deliberately kept as the ONLY
implementation so there is one thing to replace.
"""

#: Stations a customer physically waits at — the beverage queue.
BEVERAGE_STATIONS = ('Barista', 'Bar')

_RULES = (
    ('Barista', ('espresso', 'latte', 'cappuccino', 'coffee', 'flat white',
                 'cortado', 'americano', 'mocha', 'macchiato')),
    ('Bar', ('tea', 'juice', 'soda', 'cola', 'water', 'drink', 'mojito',
             'smoothie', 'shake', 'lemonade')),
    ('Pastry', ('croissant', 'cake', 'pastry', 'dessert', 'cookie',
                'cheesecake', 'muffin', 'brownie', 'tart', 'pain')),
    ('Pizza', ('pizza',)),
    ('Salad', ('salad',)),
)

DEFAULT_STATION = 'Kitchen'


def station_for(display_name, category_names=()):
    """The station for a product described by its name and POS categories.

    Order matters: the first rule that matches wins, so a "coffee cake" goes to
    Pastry only if Pastry is checked before Barista — it is not, and that is the
    documented behaviour rather than an accident. Anything unmatched is Kitchen,
    which is the safe default: a ticket at the wrong station is noticed in seconds,
    a ticket at no station is not noticed at all.
    """
    hay = (display_name or '').lower()
    if category_names:
        hay += ' ' + ' '.join(n or '' for n in category_names).lower()
    for station, words in _RULES:
        if any(w in hay for w in words):
            return station
    return DEFAULT_STATION
