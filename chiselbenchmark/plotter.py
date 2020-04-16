"""Utility for plotting test results."""

import argparse
from collections import defaultdict
import csv
import numpy as np
import os.path
import sys
import matplotlib.pyplot as plt

_TESTCASE, _DATASET, _PARAM, _CONDITION, _ROUND, _TIME = 'test', 'dataset', 'param', 'condition', 'round', 'time'


def _stats(iterable):
    """Returns mean, std for the iterable, excluding the min and max values."""
    l = sorted(iterable)[1:-1]  # drop min and max values
    return [np.mean(l), np.std(l)]


def main():
    """Main routine."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('file', help='Test results spreadsheet to be plotted')
    parser.add_argument('--save', default=False, action='store_true', help='Save plots to files named "test_case.format" in working directory')
    parser.add_argument('--show', default=False, action='store_true', help='Show each plot as it is generated')
    parser.add_argument('--format', default='png', help='Format to use when saving plot')
    parser.add_argument('--dpi', type=int, default=300, help='DPI when saving plot')
    args = parser.parse_args()

    # read results from spreadsheet
    results = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    with open(os.path.expanduser(args.file)) as csvfile:
        csvreader = csv.DictReader(csvfile)
        for row in csvreader:
            results[row[_TESTCASE]][(row[_CONDITION], row[_PARAM])][int(row[_DATASET])].append(1000*float(row[_TIME]))

    # compute mean, std
    for result in results.values():
        for condition in result.values():
            for key in condition:
                condition[key] = _stats(condition[key])

    # plot figures
    for test_case in results:
        fig, ax = plt.subplots()
        for condition_param in results[test_case]:
            datasets, stats = zip(*results[test_case][condition_param].items())
            means, errs = zip(*stats)
            fmt = '--' if condition_param[0] == 'control' else ''
            ax.errorbar(datasets, means, yerr=errs, fmt=fmt, label=f'{condition_param[0]}, n={condition_param[1]}', capsize=1.5)
            ax.set_xticks(datasets)
            ax.set_xscale('log')

        ax.set(xlabel='# rows in dataset', ylabel='time (ms)', title=f'{test_case.replace("_", " ").title()}')
        ax.legend()

        if args.show:
            plt.show()

        if args.save:
            plt.savefig(f'{test_case}.{args.format}', dpi=args.dpi, format=args.format)

    return 0


if __name__ == '__main__':
    sys.exit(main())
