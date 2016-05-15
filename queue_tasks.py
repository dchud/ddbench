import subprocess

"""
Invoke a subprocess to execute one run of ddbench on an rq queue.

For reference:

usage: ddbench - dedupe benchmarking tool [-h] [-c COUNT] [-d DATASET]
                                          [-j JOB_ID] [-p REPORT_PREFIX]
                                          [-r RELIABILITY] [-v]
"""


def run_ddbench(dataset, count=None, report_prefix=None, job_id=None,
                reliability=None, verbose=False):
    args = ['python', 'ddbench.py', '-d', dataset, '-n', '1']
    if count:
        args.extend(['-c', str(count)])
    if report_prefix:
        args.extend(['-p', report_prefix])
    if job_id:
        args.extend(['-j', str(job_id)])
    if reliability:
        args.extend(['-r', str(reliability)])
    if verbose:
        args.extend(['-v'])
    subprocess.run(args)
