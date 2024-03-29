"""Utility for generating test data for benchmarks."""

import argparse
import csv
import itertools
import os.path
import random
import string
import sys

# min/max range for generated integer values
min_int, max_int = (-99999, 99999)

# length of generated text values
text_len = 10

# Value generators for supported simple types
_gen_value = {
    str.__name__: lambda: ''.join(random.choices(string.ascii_letters + string.digits, k=text_len)),
    int.__name__: lambda: random.randint(min_int, max_int),
    float.__name__: lambda: random.random()
}


def _mangle(s):
    """A simple probabilistic string mangler."""
    r = random.random()
    if r < 0.01:
        # all title case
        return s.title()
    elif r < 0.02:
        # all lower case
        return s.lower()
    elif r < 0.03:
        # append with whitespace
        return s + ' '
    elif r < 0.04:
        # random insertion
        i = random.randint(0, len(s))
        return s[:i] + random.choice(string.ascii_lowercase) + s[i:]
    elif r < 0.05:
        # random deletion
        i = random.randint(0, len(s))
        return s[:i] + s[i+1:]
    else:
        return s


def entities(label, ctypes, termcolumns, termlistcolumns, max_termlistchoices, subconcepts, camel=False):
    """Infinite generator of test entities.

    :param label: text label for this concept of entities.
    :param ctypes: list of column types to be generated
    :param termcolumns: list of term sets used to generate corresponding columns
    :param termlistcolumns: list of term sets used to generate corresponding 'list' columns
    :param max_termlistchoices: maximum number of terms to chose per termlistcolumn
    :param subconcepts: list of subconcepts embedded in these entities
    :param camel: use came case names in the header row
    :return: a python generator that returns entities
    """
    assert(type(max_termlistchoices) == int)
    subconcepts_noheader = [subc[1:] for subc in subconcepts]
    key = 0

    # header fields
    header = [f'{label}:key'] + \
        [f'{label}:{ctype}:{i}' for i, ctype in enumerate(ctypes)] + \
        [f'{label}:term:{i}' for i, _ in enumerate(termcolumns)] + \
        [f'{label}:termlist:{i}' for i, _ in enumerate(termlistcolumns)] + \
        [cname for subconcept in subconcepts for cname in subconcept[0]]

    # came-case if needed
    header = [''.join([namepart.title() if namepart != 'key' else 'Id' for namepart in name.split(':')]) for name in header] if camel else header

    # yield header
    yield header

    # yield rows
    while True:
        yield [f'{label}:{key}'] + \
            [_gen_value[ctype]() for ctype in ctypes] + \
            [_mangle(random.choice(tc)) for tc in termcolumns] + \
            [tl for tlc in termlistcolumns for tl in [','.join(map(_mangle, random.choices(tlc, k=random.randint(0, max_termlistchoices))))]] + \
            [value for subconcept in subconcepts_noheader for value in random.choice(subconcept)]
        key = key + 1


def main():
    """Main routine."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('num', type=int, help='Number of entities to generate')
    parser.add_argument('--name', default='core', help='Name of this class of entities')
    parser.add_argument('-c', '--ctypes', nargs='*', choices=[str.__name__, int.__name__, float.__name__],
                        default=[str.__name__, int.__name__, float.__name__], help='Column types to generate')
    parser.add_argument('-t', '--terms', default='~/terms.txt', help='Filename of terms file (one term per line of text file)')
    parser.add_argument('-s', '--terms-sample-size', type=int, default=100, help='Number of terms to sample per termset created')
    parser.add_argument('--num-term-columns', type=int, default=2, help='Number of columns based on termsets to generate')
    parser.add_argument('--num-term-list-columns', type=int, default=1, help='Number of "list" columns based on termsets to generate')
    parser.add_argument('--max-term-list-choices', type=int, default=5, help='Maximum number of terms to chose per generated term list column value')
    parser.add_argument('--num-sub-concepts', type=int, default=3, help='Number of sub-concepts to generate')
    parser.add_argument('--num-sub-concept-rows', type=int, help='Number of rows per sub-concept to generate')
    parser.add_argument('--camel', action='store_true', help='Use camel case header names')
    args = parser.parse_args()

    # validate arguments
    num_rows = args.num
    ctypes = args.ctypes
    termsource_filename = args.terms
    terms_sample_size = args.terms_sample_size
    num_termcolumns = args.num_term_columns
    num_termlistcolumns = args.num_term_list_columns
    max_termlistchoices = args.max_term_list_choices
    num_subconcepts = args.num_sub_concepts
    num_subconcept_rows = args.num_sub_concept_rows or max(round(num_rows / 3), 10)

    # create term columns
    termcolumns = []
    if num_termcolumns:
        with open(os.path.expanduser(termsource_filename), 'r') as f:
            termsource = f.read().splitlines()

        for i in range(num_termcolumns):
            termcolumns.append(random.sample(termsource, terms_sample_size))

    # create term list columns
    termlistcolumns = []
    if num_termlistcolumns:
        with open(os.path.expanduser(termsource_filename), 'r') as f:
            termsource = f.read().splitlines()

        for i in range(num_termlistcolumns):
            termlistcolumns.append(random.sample(termsource, terms_sample_size))

    # create subconcepts that are just like main table but without their own subconcepts
    subconcepts = []
    for i in range(num_subconcepts):
        subconcepts.append(list(itertools.islice(entities(f'subc{i}', ctypes, termcolumns, termlistcolumns, max_termlistchoices, [], camel=args.camel), num_subconcept_rows+1)))

    csvwriter = csv.writer(sys.stdout)
    for row in itertools.islice(entities(args.name, ctypes, termcolumns, termlistcolumns, max_termlistchoices, subconcepts, camel=args.camel), num_rows+1):
        csvwriter.writerow(row)

    return 0


if __name__ == '__main__':
    sys.exit(main())
