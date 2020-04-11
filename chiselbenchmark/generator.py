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

# Value generators for support simple types
_gen_value = {
    str.__name__: lambda: ''.join(random.choices(string.ascii_letters + string.digits, k=text_len)),
    int.__name__: lambda: random.randint(min_int, max_int),
    float.__name__: lambda: random.random()
}


def _mangle(s):
    """A simple probabilistic string mangler."""
    r = random.random()
    if r < 0.1:
        # all upper
        return s.upper()
    elif r < 0.2:
        # all lower
        return s.lower()
    elif r < 0.3:
        # append with whitespace
        return s + ' ' * random.randint(1,3)
    elif r < 0.4:
        # random insertion
        i = random.randint(0, len(s))
        return s[:i] + random.choice(string.ascii_letters) + s[i:]
    elif r < 0.5:
        # random deletion
        i = random.randint(0, len(s))
        return s[:i] + s[i+1:]
    else:
        return s


def entities(label, ctypes, termcolumns, subconcepts):
    """Infinite generator of test entities.

    :param label: text label for this concept of entities.
    :param ctypes: list of column types to be generated
    :param termcolumns: list of term sets used to generate corresponding columns
    :param subconcepts: list of subconcepts embedded in these entities
    :return: a python generator that returns entities
    """
    key = 0

    # yield header
    yield [f'{label}:key'] + \
        [f'{label}:{ctype}:{i}' for i, ctype in enumerate(ctypes)] + \
        [f'{label}:term:{i}' for i, _ in enumerate(termcolumns)] + \
        [cname for subconcept in subconcepts for cname in subconcept[0]]

    # yield rows
    while True:
        yield [key] + \
            [_gen_value[ctype]() for ctype in ctypes] + \
            [_mangle(random.choice(tc)) for tc in termcolumns] + \
            [value for subconcept in subconcepts for value in random.choice(subconcept[1:])]
        key = key + 1


def main():
    """Main routine."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('num', type=int, help='Number of entities to generate')
    parser.add_argument('--name', default='data', help='Name of this class of entities')
    parser.add_argument('-c', '--ctypes', nargs='*', choices=[str.__name__, int.__name__, float.__name__],
                        default=[str.__name__, int.__name__, float.__name__], help='Column types to generate')
    parser.add_argument('-t', '--terms', default='~/terms.txt', help='Filename of terms file (one term per line of text file)')
    parser.add_argument('-s', '--terms-sample-size', type=int, help='Number of terms to sample per termset created')
    parser.add_argument('--num-term-columns', type=int, default=1, help='Number of columns based on termsets to generate')
    parser.add_argument('--num-sub-concepts', type=int, default=1, help='Number of sub-concepts to generate')
    parser.add_argument('--num-sub-concept-rows', type=int, help='Number of rows per sub-concept to generate')
    args = parser.parse_args()

    # validate arguments
    num_rows = args.num
    ctypes = args.ctypes
    termsource_filename = args.terms
    terms_sample_size = args.terms_sample_size or max(round(num_rows / 10), 10)
    num_termcolumns = args.num_term_columns
    num_subconcepts = args.num_sub_concepts
    num_subconcept_rows = args.num_sub_concept_rows or max(round(num_rows / 2), 10)

    # create term columns
    termcolumns = []
    if num_termcolumns:
        with open(os.path.expanduser(termsource_filename), 'r') as f:
            termsource = f.read().splitlines()

        for i in range(num_termcolumns):
            termcolumns.append(random.sample(termsource, terms_sample_size))

    # create subconcepts that are just like main table but without their own subconcepts
    subconcepts = []
    for i in range(num_subconcepts):
        subconcepts.append(list(itertools.islice(entities(f'subc{i}', ctypes, termcolumns, []), num_subconcept_rows+1)))

    csvwriter = csv.writer(sys.stdout)
    for row in itertools.islice(entities(args.name, ctypes, termcolumns, subconcepts), num_rows+1):
        csvwriter.writerow(row)

    return 0


if __name__ == '__main__':
    sys.exit(main())
