A performance and accuracy benchmarking tool for the dedupe
library for data deduplication and entity resolution.

  https://github.com/datamade/dedupe

Our intent is to provide a reliable end-to-end benchmark suite
for use on multiple platforms.

The datasets included under data/ are graciously made available by 
Database Group Leipzig:

  http://dbs.uni-leipzig.de/en/research/projects/object_matching/fever/benchmark_datasets_for_entity_resolution

## Current status

This is a nascent app lacking much refinement.  So far the datasets 
above have been prepped for ready use in benchmarking and stored in
the `data/` directory.  The app itself is configured with a YAML file
that details the contents of each dataset and their corresponding
field structures and mapping details for use with dedupe.  This 
configuration is based on [confire](https://github.com/bbengfort/confire)
which is included as a dependency, and the details are in 
`conf/ddbench.yaml`.

Our intent is to wrap the basic `ddbench.py` script, which processes
one dataset one time, with sufficient instrumentation to enable
multiple runs, report generation, and calculations of accuracy and
performance metrics.  This work is pending.

`ddbench.py` uses the provided perfect match files to auto-label a
training set drawn from a random sample during each run of dedupe.
It defaults to exact precision, and a reliability option may be 
given to introduce simulated operator error during training.


## Basic usage

ddbench assumes a Python 3.5+ environment.  Ideally using a Python
virtual environment, first activate and prep that environment using pip:

    % pyvenv ENV
    % source ENV/bin/activate
    (ENV) % pip install -r requirements.txt

To initiate a single run of the ddbench script, specify one of the
provided datasets using the `--dataset` option:

    % ./ddbench.py --dataset=abt-buy
    % ./ddbench.py --dataset=amazon-googleproducts
    % ./ddbench.py --dataset=dblp-acm
    % ./ddbench.py --dataset=dblp-scholar

The script in its current primitive form will output a lot of debugging
info that should reassure you that it at least is working.  We will
improve upon this shortly.

You may also specify `--count`, the number of pairs to auto-label,
and `--reliability`, a number between 0.0-1.0 indicating the
reliability of a simulated human trainer.  By default, the auto-label
process will always choose the right decision about a training pair;
if you set `--reliability=0.98`, for example, it will be correct only
98% of the time.

For example, to time the entire run using the Abt-Buy dataset with
a 99% accurate trainer and 100 training pairs:

    % time ./ddbench.py --count=100 --reliability=0.99 --dataset=abt-buy


## Multiple runs

ddbench can use [rq](http://python-rq.org/) to run multiple ddbench
jobs in parallel.  A single run as described above will execute
directly; with [Redis](http://redis.io/) installed and running, you
can specify multiple runs with additional options.

First, install Redis and start the server if it is not already
running:

    % redis-server &

Second, (within your virtualenv or equivalent) begin one or more
rq queue workers.  It can be easy to run these in multiple terminal
windows:

    % rq worker

Each worker you execute will wait for jobs to be added to the queue,
and take an available job when they are idle.  You can run as many
workers as you want; a good rule of thumb might be to run as many
workers as the number of cores your machine has available minus one.

Finally, use the `--num_runs` option to specify a positive integer
number of runs to execute:

    % ./ddbench.py --num_runs=20 --count=10 --dataset=abt-buy

ddbench will immediately queue up all 20 runs, and each worker will
take one at a time, with each queued job equating to exactly one
dedupe run.

A shared report name prefix will be used to store dedupe run timing
and accuracy details.  The id of each individual run within that
batch execution will be appended to each file as well.  For example, 
if you specify six runs like this:

    % ./ddbench.py --num_runs=6 --count=50 --dataset=abt-buy

When all of the queued jobs complete, you should have something like
the following in your `report/` directory:

    16:47 $ ls -l report/
    total 216
    -rw-r--r--  1 dchud  staff  105 May 15 15:55 201605151553-790ee6-abt-buy-001.json
    -rw-r--r--  1 dchud  staff  105 May 15 15:56 201605151553-790ee6-abt-buy-002.json
    -rw-r--r--  1 dchud  staff  105 May 15 15:56 201605151553-790ee6-abt-buy-003.json
    -rw-r--r--  1 dchud  staff  105 May 15 15:57 201605151553-790ee6-abt-buy-004.json
    -rw-r--r--  1 dchud  staff  105 May 15 15:58 201605151553-790ee6-abt-buy-005.json
    -rw-r--r--  1 dchud  staff  106 May 15 15:58 201605151553-790ee6-abt-buy-006.json

A setting for `report_dir` is present in `config/ddbench.yaml`.

TODO:  next steps are to fill out the reported data and to gather and
analyze the results.  This work remains in process.
