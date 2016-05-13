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
