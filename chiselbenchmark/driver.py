"""Utility for driving benchmark tests."""

import argparse
import gc
import time
import os
import shutil
import sys
import chisel

# Test conditions
_CONDITION_OPTIMIZED = 'optimized'
_CONDITION_CONTROL = 'control'
_all_conditions = _default_conditions = [
    _CONDITION_CONTROL,
    _CONDITION_OPTIMIZED
]

# Test dataset column name parts
_CORE, _SUBC, _CONC = 'core', 'subc', 'conc'
_INT, _FLOAT, _TEXT = 'int', 'float', 'text'
_TERM, _TERMLIST = 'term', 'termlist'
_KEY = 'key'
_EXT = '.csv'


class LocalCatalogBaseTest:
    """Base class for local catalog test suites."""

    def __init__(self):
        super(LocalCatalogBaseTest).__init__()
        self.catalog = None
        self._output_schema = 'output'
        self._catalog_path = None
        self._output_path = None
        self._table_name = None

    @property
    def table_name(self):
        return self._table_name

    @table_name.setter
    def table_name(self, value):
        self._table_name = f'{value}{_EXT}'

    @property
    def catalog_path(self):
        return self._catalog_path

    @catalog_path.setter
    def catalog_path(self, value):
        self._catalog_path = value
        self._output_path = os.path.join(self._catalog_path, self._output_schema)

    def setUp(self):
        os.makedirs(self._output_path, exist_ok=True)
        self.catalog = chisel.connect(f'file://{os.path.expanduser(self.catalog_path)}')

    def tearDown(self):
        shutil.rmtree(self._output_path, ignore_errors=True)


class TestCore (LocalCatalogBaseTest):
    """Core test suite for benchmarks."""

    def test_case_reify_n_concepts(self, condition, n=1):
        """Normalizes N concepts."""
        t = self.catalog['.'][self.table_name]
        with self.catalog.evolve(consolidate=(condition != _CONDITION_CONTROL)):
            exclude_from_altered = []
            # reify concepts
            for i in range(n):
                # non key columns to reify into new concept
                nonkey_columns = [t[cname] for cname in t.columns if cname.startswith(f'{_SUBC}{i}:') and _KEY not in cname]
                # reify key, nonkeys
                subc = t.reify({t[f'{_SUBC}{i}:{_KEY}']}, set(nonkey_columns))
                # assign to catalog
                self.catalog[self._output_schema][f'{_CONC}{i}{_EXT}'] = subc
                # remember nonkeys for exclusion from altered original table
                exclude_from_altered.extend([c.name for c in nonkey_columns])

            # alter original
            altered = t.select(*[t[cname] for cname in t.columns if cname not in exclude_from_altered])
            self.catalog[self._output_schema][f'{_CORE}{_EXT}'] = altered

    def test_case_reify_n_subconcepts(self, condition, n=1):
        """Normalizes N subconcepts."""
        t = self.catalog['.'][self.table_name]
        with self.catalog.evolve(consolidate=(condition != _CONDITION_CONTROL)):
            exclude_from_altered = []
            # reify subconcepts
            for i in range(n):
                # list of columns to be reified
                columns = [t[cname] for cname in t.columns if cname.startswith(f'{_SUBC}{i}:')]
                exclude_from_altered.extend([c.name for c in columns])
                # reify subconcept columns
                subc = t.reify_sub(*columns)
                # assign to catalog
                self.catalog[self._output_schema][f'{_SUBC}{i}{_EXT}'] = subc

            # alter original
            altered = t.select(*[t[cname] for cname in t.columns if cname not in exclude_from_altered])
            self.catalog[self._output_schema][f'{_CORE}{_EXT}'] = altered

    def test_case_reify_n_subconcepts_and_merge(self, condition, n=2):
        """Normalize N subconcepts and merge them into one."""
        t = self.catalog['.'][self.table_name]
        with self.catalog.evolve(consolidate=(condition != _CONDITION_CONTROL)):
            exclude_from_altered = []
            subc0 = None
            # reify subconcepts
            for i in range(n):
                # list of columns to be reified
                columns = [t[cname] for cname in t.columns if cname.startswith(f'{_SUBC}{i}:')]
                exclude_from_altered.extend([c.name for c in columns])
                # reify ith subconcept
                subci = t.reify_sub(*columns)
                # merge subconcepts
                if i == 0:
                    subc0 = subci
                else:
                    subci = subci.select(*[
                        subci[cname].alias(cname.replace(f'{_SUBC}{str(i)}', f'{_SUBC}0')) for cname in subci.columns
                    ])
                    subc0 = subc0 + subci

            # assign to catalog
            self.catalog[self._output_schema][f'{_SUBC}0{_EXT}'] = subc0

            # alter original
            altered = t.select(*[t[cname] for cname in t.columns if cname not in exclude_from_altered])
            self.catalog[self._output_schema][f'{_CORE}{_EXT}'] = altered

    def test_case_reify_concept_and_n_subconcepts(self, condition, n=1):
        """Normalizes 1 concept and N subconcepts."""
        t = self.catalog['.'][self.table_name]
        with self.catalog.evolve(consolidate=(condition != _CONDITION_CONTROL)):
            exclude_from_altered = []

            # reify concept
            for i in range(1):
                # non key columns to reify into new concept
                nonkey_columns = [t[cname] for cname in t.columns if cname.startswith(f'{_SUBC}{i}:') and _KEY not in cname]
                exclude_from_altered.extend([c.name for c in nonkey_columns])
                # reify key, nonkeys
                subc = t.reify({t[f'{_SUBC}{i}:{_KEY}']}, set(nonkey_columns))
                # assign to catalog
                self.catalog[self._output_schema][f'{_CONC}{i}{_EXT}'] = subc

            # reify subconcepts
            for i in range(1, n + 1):
                # list of columns to be reified
                columns = [t[cname] for cname in t.columns if cname.startswith(f'{_SUBC}{i}:')]
                exclude_from_altered.extend([c.name for c in columns])
                # reify subconcept columns
                subc = t.reify_sub(*columns)
                # assign to catalog
                self.catalog[self._output_schema][f'{_SUBC}{i}{_EXT}'] = subc

            # alter original
            altered = t.select(*[t[cname] for cname in t.columns if cname not in exclude_from_altered])
            self.catalog[self._output_schema][f'{_CORE}{_EXT}'] = altered

    def test_case_create_n_domains_from_n_columns(self, condition, n=1):
        """Create N domains."""
        t = self.catalog['.'][self.table_name]
        term_columns = [t[cname] for cname in t.columns if cname.find(_TERM) >= 0 > cname.find(_TERMLIST)]
        assert(n <= len(term_columns))
        with self.catalog.evolve(consolidate=(condition != _CONDITION_CONTROL)):
            for i in range(n):
                self.catalog[self._output_schema][f'{_TERM}{i}{_EXT}'] = term_columns[i].to_domain()

    def test_case_create_n_vocabularies_from_n_columns(self, condition, n=1):
        """Create N vocabularies."""
        t = self.catalog['.'][self.table_name]
        term_columns = [t[cname] for cname in t.columns if cname.find(_TERM) >= 0 > cname.find(_TERMLIST)]
        assert(n <= len(term_columns))
        with self.catalog.evolve(consolidate=(condition != _CONDITION_CONTROL)):
            for i in range(n):
                self.catalog[self._output_schema][f'{_TERM}{i}{_EXT}'] = term_columns[i].to_vocabulary()

    def test_case_create_n_relations_from_nested_values(self, condition, n=1):
        """Create N relations from nested values (i.e., non-atomic values)."""
        t = self.catalog['.'][self.table_name]
        list_columns = [t[cname] for cname in t.columns if cname.find(_TERMLIST) >= 0]
        assert(n <= len(list_columns))
        with self.catalog.evolve(consolidate=(condition != _CONDITION_CONTROL)):
            for i in range(n):
                self.catalog[self._output_schema][f'{_TERMLIST}{i}{_EXT}'] = list_columns[i].to_atoms()

    def test_case_reify_n_subconcepts_and_create_domain_from_columns(self, condition, n=1):
        """Normalizes N subconcepts and creates a new domain from N like columns from subconcepts."""
        t = self.catalog['.'][self.table_name]
        with self.catalog.evolve(consolidate=(condition != _CONDITION_CONTROL)):
            exclude_from_altered = []
            term = None
            # reify subconcepts
            for i in range(n):
                # list of columns to be reified
                columns = [t[cname] for cname in t.columns if cname.startswith(f'{_SUBC}{i}:')]
                exclude_from_altered.extend([c.name for c in columns])
                # reify subconcept columns
                subc = t.reify_sub(*columns)
                # assign to catalog
                self.catalog[self._output_schema][f'{_SUBC}{i}{_EXT}'] = subc
                # collect up term columns and merge
                termi = subc.select(subc[f'{_SUBC}{i}:{_TERM}:0'].alias(_TERM))
                if i == 0:
                    term = termi
                else:
                    term = term + termi

            # create domain
            dom = term[_TERM].to_domain()
            self.catalog[self._output_schema][f'{_TERM}{_EXT}'] = dom

            # alter original
            altered = t.select(*[t[cname] for cname in t.columns if cname not in exclude_from_altered])
            self.catalog[self._output_schema][f'{_CORE}{_EXT}'] = altered

    def test_case_create_vocabulary_then_align_and_tag(self, condition, n=1):
        """Create a vocab from one termlist, then use it to create tags out of n other termlists."""
        t = self.catalog['.'][self.table_name]
        with self.catalog.evolve(consolidate=(condition != _CONDITION_CONTROL)):
            # create canonical vocabulary from core termlist
            src_column = f'{_CORE}:{_TERMLIST}:0'
            vocab = t[src_column].to_atoms().columns[src_column].to_vocabulary()
            self.catalog[self._output_schema][f'vocab{_EXT}'] = vocab

            # align and tag from subconcept termlists
            exclude_from_altered = []
            for i in range(n):
                # column to be aligned and tagified
                column = t[f'{_SUBC}{i}:{_TERMLIST}:0']
                exclude_from_altered.append(column.name)
                tags = column.to_tags(vocab)
                self.catalog[self._output_schema][f'{_SUBC}{i}-tags{_EXT}'] = tags

            # alter original
            altered = t.select(*[t[cname] for cname in t.columns if cname not in exclude_from_altered])
            self.catalog[self._output_schema][f'{_CORE}{_EXT}'] = altered


# Default test suite
_default_test_suite = TestCore

# All test cases and default params for each
_test_cases_and_params = {
    'reify_n_concepts': [1, 2, 3],
    'reify_n_subconcepts': [1, 2, 3],
    'reify_n_subconcepts_and_merge': [2, 3],
    'reify_concept_and_n_subconcepts': [1, 2],
    'create_n_domains_from_n_columns': [1, 2, 4],
    'create_n_vocabularies_from_n_columns': [1, 2, 4],
    'create_n_relations_from_nested_values': [1, 2, 4],
    'reify_n_subconcepts_and_create_domain_from_columns': [1, 2, 3],
    'create_vocabulary_then_align_and_tag': [1, 2]
}
# Default tests cases, exclude the most expensive test case(s)
_default_test_cases = _test_cases_and_params.keys() - ['create_vocabulary_then_align_and_tag']


def main():
    """Main routine."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('rounds', type=int, help='Number of rounds per test case')
    parser.add_argument('dataset', nargs='+', help='Datasets to be used for source table of each test')
    parser.add_argument('--sleep', type=int, default=1, help='Number of seconds to sleep between test cases')
    parser.add_argument('--catalog-path', default='~/benchmarks', help='Catalog path')
    parser.add_argument('--disable-teardown', default=False, action='store_true', help='Disable teardown for debug purposes')
    parser.add_argument('--conditions', nargs='+', choices=_all_conditions, default=_default_conditions, help='Conditions to be tested')
    parser.add_argument('--testcases', nargs='+', choices=_test_cases_and_params.keys(), default=_default_test_cases, help='Test cases to be run')
    parser.add_argument('--params', nargs='+', type=int, help='Parameters for the test cases')
    args = parser.parse_args()

    # validate the disable teardown debug setting
    if args.disable_teardown and (args.rounds > 1 or len(args.testcases) > 1 or len(args.conditions) > 1 or not args.params or len(args.params) > 1):
        parser.error('Disable teardown can only be used with a single (round, test case, condition, param) for debug purposes only')

    # load and configure test suite
    test_suite = _default_test_suite()
    test_suite.catalog_path = os.path.expanduser(args.catalog_path)

    # disable automatic garbage collection
    gc.disable()

    # output header and commence tests
    print('test,dataset,param,condition,round,time')
    for test_case in args.testcases:
        for dataset in args.dataset:
            test_suite.table_name = dataset
            params = args.params or _test_cases_and_params[test_case]
            for param in params:
                for condition in args.conditions:
                    for i in range(args.rounds):
                        # setup
                        test_suite.setUp()
                        test_case_fn = getattr(test_suite, f'test_case_{test_case}')

                        # measure time and run test case
                        s = time.process_time()
                        test_case_fn(condition, n=param)
                        t = (time.process_time() - s)

                        # output results
                        print(f'{test_case},{dataset},{param},{condition},{i},{t}')

                        # teardown (optional)
                        if not args.disable_teardown:
                            test_suite.tearDown()

                        # force garbage collect, and sleep (just to let system settle down before next round)
                        gc.collect()
                        time.sleep(args.sleep)

    return 0


if __name__ == '__main__':
    sys.exit(main())
