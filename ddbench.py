#!/usr/bin/env python

import argparse
from collections import defaultdict
import csv
import hashlib
import json
import logging
from random import random
import re
import time

from redis import Redis
from rq import Queue
from unidecode import unidecode

import dedupe

from config import settings
from queue_tasks import run_ddbench


def time_hash(digits=6):
    """Generate an arbitrary hash based on the current time for filenames."""
    hash = hashlib.sha1()
    hash.update(str(time.time()).encode())
    t = time.localtime()
    dt = '%s%02d%02d%02d%02d' % (t.tm_year, t.tm_mon, t.tm_mday,
                                 t.tm_hour, t.tm_min)
    return '%s-%s' % (dt, hash.hexdigest()[:digits])


def pre_process(v):
    """Clean up data on the way in, following the lead of the
    record linkage example in dedupe-examples."""

    v = unidecode(v)
    v = re.sub('[\n/:]', ' ', v)
    v = re.sub("[-',]", '', v)
    v = re.sub(' +', ' ', v)
    v = v.strip().strip('"').strip("'").strip().lower()
    return v or None


def corpus_generator(fname, encoding='utf-8'):
    with open(fname, encoding=encoding) as corpus_input:
        for row in corpus_input:
            yield pre_process(row)


def load_csv(fname, return_type=dict, encoding='utf-8', field_map={}):
    d = return_type()
    with open(fname, encoding=encoding) as csvfile:
        reader = csv.DictReader(csvfile)
        for i, row in enumerate(reader):
            clean_row = dict([(field_map.get(k, k), pre_process(v))
                              for k, v in row.items()])
            if clean_row.get('price', ''):
                v_price = clean_row['price'].replace('$', '')
                v_price = v_price.replace(' gbp', '')
                try:
                    clean_row['price'] = float(v_price)
                except:
                    logging.debug('v_price: %s' % v_price)
            if isinstance(d, list):
                d.append(clean_row)
            else:
                d[str(i)] = clean_row
    return d


def auto_label(deduper, m1, m2, reliability, count=100):
    """
    Given a deduper and match files, automatically label <count>
    uncertain pairs according to the given reliability.
    """

    # FIXME: how many?
    for i in range(count):
        n_match, n_distinct = (len(deduper.training_pairs['match']),
                               len(deduper.training_pairs['distinct']))
        uncertain_pairs = deduper.uncertainPairs()
        labels = {'distinct': [], 'match': []}

        for record_pair in uncertain_pairs:
            r0 = record_pair[0]
            r1 = record_pair[1]
            is_match = False
            # TODO: which order are they in?
            id1 = r0['id']
            id2 = r1['id']
            if id2 in m1[id1]:
                is_match = True
            elif id1 in m2[id2]:
                is_match = True
            if random() > reliability:
                # lie about match; no effect if reliability == 1.0
                is_match = 1 - is_match

            logging.debug('match: ' + str(is_match))
            if is_match:
                labels['match'].append(record_pair)
            else:
                labels['distinct'].append(record_pair)
            # TODO: what about uncertainty?  should we fake some?

            logging.debug("{0} positive, {1} negative".format(
                    n_match, n_distinct))

        deduper.markPairs(labels)


def run_dedupe(args, dataset):
    """Complete a single run of dedupe on the specified dataset."""

    # read in the datasets, assuming two for record linkage
    input_files = dataset['input_files']
    if len(input_files) != 2:
        parser.error('--dataset has != 2 input files')

    path = dataset['path']
    f1 = dataset['input_files'][0]
    data_file_1 = f1['data_file']
    field_map_1 = f1.get('field_map', {})
    encoding_1 = f1.get('encoding', 'utf-8')
    input_file_1 = load_csv('%s/%s' % (path, data_file_1), encoding=encoding_1,
                            field_map=field_map_1)

    f2 = dataset['input_files'][1]
    data_file_2 = f2['data_file']
    field_map_2 = f2.get('field_map', {})
    encoding_2 = f2.get('encoding', 'utf-8')
    input_file_2 = load_csv('%s/%s' % (path, data_file_2), encoding=encoding_2,
                            field_map=field_map_2)

    # parse field definitions
    fields = []
    for field_spec in dataset['fields']:
        field = {'field': field_spec['field'], 'type': field_spec['type']}
        if 'has_missing' in field_spec.keys():
            field['has missing'] = field_spec['has_missing']
        if 'corpus_file' in field_spec.keys():
            corpus_path = '%s/%s' % (path, field_spec['corpus_file'])
            encoding = dataset.get('encoding', 'utf-8')
            field['corpus'] = corpus_generator(corpus_path, encoding=encoding)
        fields.append(field)

    logging.debug('Sampling')
    linker = dedupe.RecordLink(fields)
    # FIXME: 15000 is hard-coded and arbitrary, copied from dedupe example
    linker.sample(input_file_1, input_file_2, 15000)

    logging.debug('Loading match file')
    # read in the match file now so we can auto-label
    matches = load_csv('%s/%s' % (path, dataset['match_file']), list)

    match_count = 0
    # create fast lookup for each set of matching identifiers from one
    # to the other, e.g. "if id2 in m1[id1]"
    match_set_1 = defaultdict(set)
    match_set_2 = defaultdict(set)

    match_id_1 = dataset['input_files'][0]['match_id']
    match_id_2 = dataset['input_files'][1]['match_id']

    for m in matches:
        match_count += 1
        match_set_1[m[match_id_1]].add(m[match_id_2])
        match_set_2[m[match_id_2]].add(m[match_id_1])

    logging.debug('Auto-labeling')
    auto_label(linker, match_set_1, match_set_2, args.reliability,
               count=args.count)

    logging.debug('Training')
    linker.train()

    logging.debug('Matching')
    # FIXME: third param "0" is hard-coded
    linked_records = linker.match(input_file_1, input_file_2, 0)

    logging.debug('Reviewing linked records')

    linked_records_count = 0
    correct_count = incorrect_count = 0
    for cluster, score in linked_records:
        linked_records_count += 1
        logging.debug('cluster %s, score %s' % (cluster, score))
        is_correct = False
        id1, id2 = cluster
        r1 = input_file_1[id1]
        r2 = input_file_2[id2]
        if r2['id'] in match_set_1[r1['id']]:
            is_correct = True
        if r1['id'] in match_set_2[r2['id']]:
            is_correct = True
        if is_correct:
            correct_count += 1
            logging.debug('CORRECT')
        else:
            incorrect_count += 1
            logging.debug('INCORRECT')

    report = {
            'match_count': match_count,
            'linked_records_count': linked_records_count,
            'correct_count': correct_count,
            'incorrect_count': incorrect_count
        }

    # Generate a distinct filename for report, allowing for grouping
    report_path = '%s/%s-%s-%03d.json' % (settings.get('report_dir'),
                                          args.report_prefix, args.dataset,
                                          args.job_id)

    with open(report_path, 'w') as fp_report:
        json.dump(report, fp_report, indent=2)
    logging.info('Wrote report to %s' % report_path)


if __name__ == '__main__':
    parser = argparse.ArgumentParser('ddbench - dedupe benchmarking tool')
    parser.add_argument('-c', '--count', dest='count',
                        default=50, type=int,
                        help='number of uncertain pairs to auto-label')
    parser.add_argument('-d', '--dataset', dest='dataset', default=None,
                        help='name of dataset to dedupe (see data/)')
    parser.add_argument('-j', '--job-id', dest='job_id',
                        default=1, type=int,
                        help='id for this benchmark run within larger set')
    parser.add_argument('-n', '--num_runs', dest='num_runs',
                        default=1, type=int,
                        help='number of repeat runs to perform')
    parser.add_argument('-p', '--report-prefix', dest='report_prefix',
                        default=time_hash(),
                        help='directory path to report output')
    parser.add_argument('-r', '--reliability', dest='reliability',
                        default=1.0, type=float,
                        help='Reviewer "reliability" (0.0-1.0, default 1.0)')
    parser.add_argument('-v', '--verbose', dest='verbose', default=False,
                        action='store_true')

    args = parser.parse_args()
    if args.verbose or settings.get('DEBUG'):
        logging.getLogger().setLevel(logging.DEBUG)

    if args.reliability < 0.0 and args.reliability > 1.0:
        parser.error('Reliability must be within [0.0, 1.0]')

    datasets = settings.get('datasets', {})
    try:
        dataset = datasets[args.dataset]
    except KeyError:
        parser.error('Please specify a --dataset from those provided in data/')

    # A single run can come from a command line or queued invocation
    if args.num_runs == 1:
        run_dedupe(args, dataset)
    elif args.num_runs > 1:
        redis_conn = Redis()
        q = Queue(connection=redis_conn)
        # Start the job ids at 1 for clarity
        for i in range(1, args.num_runs + 1):
            # in queued mode, report_prefix and job_id are required
            subprocess_args = [args.dataset, args.count, args.report_prefix,
                               i, args.reliability,
                               args.verbose or settings.get('debug')]
            # Large dedupe jobs can take >30min so set a sufficient timeout
            q.enqueue(run_ddbench, args=subprocess_args,
                      timeout=settings.get('max_timeout', 60 * 60))
            logging.debug('Queued job # %s' % i)
        queue_length = len(q)
        while queue_length > 0:
            logging.debug('%s of %s jobs remain on the queue' % (queue_length,
                          args.num_runs))
            time.sleep(settings.get('polling_interval', 30))
            queue_length = len(q)
        logging.debug('Queue is empty; all jobs are active or complete.')
        logging.debug('Reports are in %s/ with prefix %s' % (
                      settings.get('report_dir'), args.report_prefix))
