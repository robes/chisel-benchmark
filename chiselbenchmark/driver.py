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
_DATA, _SUBC = 'data', 'subc'
_INT, _FLOAT, _TEXT = 'int', 'float', 'text'
_TERM, _TERMLIST = 'term', 'termlist'
_KEY = 'key'


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

    def test_case_reify_two_concepts(self, condition):
        t = self.catalog['.'][self.table_name]
        subc0 = t.reify({t['subc0:key']}, {t['subc0:int:0'], t['subc0:term:2']})
        subc1 = t.reify({t['subc1:key']}, {t['subc1:int:0'], t['subc1:term:2']})
        with self.catalog.evolve(consolidate=(condition != _CONDITION_CONTROL)):
            self.catalog[self._output_schema]['subc0.csv'] = subc0
            self.catalog[self._output_schema]['subc1.csv'] = subc1


# Default test suite and test cases
_default_test_suite = TestCore
_default_test_cases = _all_test_cases = [
    'reify_two_concepts'
]


def main():
    """Main routine."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('dataset', help='Name of dataset table to be used')
    parser.add_argument('rounds', type=int, help='Number of rounds per test case')
    parser.add_argument('--sleep', type=int, default=1, help='Number of seconds to sleep between test cases')
    parser.add_argument('--catalog-path', default='~/benchmarks', help='Catalog path')
    parser.add_argument('--disable-teardown', default=False, action='store_true', help='Disable teardown for debug purposes')
    parser.add_argument('--conditions', nargs='*', choices=_all_conditions, default=_default_conditions, help='Conditions to be tested')
    parser.add_argument('--testcases', nargs='*', choices=_all_test_cases, default=_default_test_cases, help='Test cases to be run')
    args = parser.parse_args()

    # validate the disable teardown debug setting
    if args.disable_teardown and (args.rounds > 1 or len(args.testcases) > 1 or len(args.conditions) > 1):
        parser.error('Disable teardown can only be used with a single (round, single test case, condition) for debug purposes only')

    # load and configure test suite
    test_suite = _default_test_suite()
    test_suite.catalog_path = os.path.expanduser(args.catalog_path)
    test_suite.table_name = args.dataset
    test_cases = _default_test_cases

    # disable automatic garbage collection
    gc.disable()

    # output header and commence tests
    print('test,dataset,condition,round,time')
    for test_case in test_cases:
        for condition in args.conditions:
            for i in range(args.rounds):
                # setup
                test_suite.setUp()
                test_case_fn = getattr(test_suite, f'test_case_{test_case}')

                # measure time and run test case
                s = time.process_time()
                test_case_fn(condition)
                t = (time.process_time() - s)

                # output results
                print(f'{test_case},{args.dataset},{condition},{i},{t}')

                # teardown (optional)
                if not args.disable_teardown:
                    test_suite.tearDown()

                # force garbage collect, and sleep (just to let system settle down before next round)
                gc.collect()
                time.sleep(args.sleep)

    return 0


if __name__ == '__main__':
    sys.exit(main())
