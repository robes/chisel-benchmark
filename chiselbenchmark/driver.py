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
        self._table_name = value

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


# Default test suite
_default_test_suite = TestCore

# Default test cases and params
_test_cases_and_params = {
    'reify_n_concepts': [1, 2, 3],
    'reify_n_subconcepts': [1, 2, 3],
    'reify_n_subconcepts_and_merge': [2, 3],
    'reify_concept_and_n_subconcepts': [1, 2],
    'create_n_domains_from_n_columns': [1, 2, 4],
    'create_n_vocabularies_from_n_columns': [1, 2, 4]
}


def main():
    """Main routine."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('dataset', help='Name of dataset table to be used')
    parser.add_argument('rounds', type=int, help='Number of rounds per test case')
    parser.add_argument('--sleep', type=int, default=1, help='Number of seconds to sleep between test cases')
    parser.add_argument('--catalog-path', default='~/benchmarks', help='Catalog path')
    parser.add_argument('--disable-teardown', default=False, action='store_true', help='Disable teardown for debug purposes')
    parser.add_argument('--conditions', nargs='*', choices=_all_conditions, default=_default_conditions, help='Conditions to be tested')
    parser.add_argument('--testcases', nargs='*', choices=_test_cases_and_params.keys(), default=_test_cases_and_params.keys(), help='Test cases to be run')
    parser.add_argument('--params', nargs='*', type=int, help='Parameters for the test cases')
    args = parser.parse_args()

    # validate the disable teardown debug setting
    if args.disable_teardown and (args.rounds > 1 or len(args.testcases) > 1 or len(args.conditions) > 1 or not args.params or len(args.params) > 1):
        parser.error('Disable teardown can only be used with a single (round, test case, condition, param) for debug purposes only')

    # load and configure test suite
    test_suite = _default_test_suite()
    test_suite.catalog_path = os.path.expanduser(args.catalog_path)
    test_suite.table_name = args.dataset

    # disable automatic garbage collection
    gc.disable()

    # output header and commence tests
    print('test,dataset,param,condition,round,time')
    for test_case in args.testcases:
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
                    print(f'{test_case},{args.dataset},{param},{condition},{i},{t}')

                    # teardown (optional)
                    if not args.disable_teardown:
                        test_suite.tearDown()

                    # force garbage collect, and sleep (just to let system settle down before next round)
                    gc.collect()
                    time.sleep(args.sleep)

    return 0


if __name__ == '__main__':
    sys.exit(main())
