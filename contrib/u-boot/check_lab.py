#!/usr/bin/env python3
"""Check sjg-lab board reliability across recent GitLab pipelines."""

import argparse
import configparser
import concurrent.futures
import json
import os
import re
import sys
import urllib.parse
import urllib.request
from collections import defaultdict

sys.path.insert(0, os.path.join(os.environ['HOME'], 'u', 'tools'))
from u_boot_pylib import tout

BASE = 'https://concept.u-boot.org'
PROJECT = 'u-boot/u-boot'
API = f'{BASE}/api/v4/projects/{urllib.parse.quote(PROJECT, safe="")}'

# Number of parallel requests
NUM_WORKERS = 8


def get_token():
    conf = configparser.ConfigParser()
    conf.read(os.path.expanduser('~/.config/pickman.conf'))
    return conf.get('gitlab', 'token')


TOKEN = get_token()


def api_get(path):
    """Fetch JSON from the GitLab API."""
    url = f'{API}{path}'
    req = urllib.request.Request(url)
    req.add_header('PRIVATE-TOKEN', TOKEN)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())


def get_job_log(job_id):
    """Get the last 50 lines of a job's log."""
    url = f'{API}/jobs/{job_id}/trace'
    req = urllib.request.Request(url)
    req.add_header('PRIVATE-TOKEN', TOKEN)
    with urllib.request.urlopen(req, timeout=30) as resp:
        text = resp.read().decode('utf-8', errors='replace')
    text = re.sub(r'\x1b\[[0-9;]*m', '', text)
    lines = text.strip().split('\n')
    return '\n'.join(lines[-50:])


def fetch_pipeline_jobs(pipe):
    """Fetch sjg-lab jobs for a single pipeline.

    Returns:
        list of (pipeline_id, job_dict) tuples
    """
    pid = pipe['id']
    if pipe['status'] == 'skipped':
        return []

    results = []
    page = 1
    while True:
        jobs = api_get(
            f'/pipelines/{pid}/jobs?per_page=100&page={page}')
        if not jobs:
            break
        for job in jobs:
            if (job.get('stage') == 'sjg-lab'
                    and job['status'] not in ('manual', 'canceled')):
                results.append((pid, job))
        if len(jobs) < 100:
            break
        page += 1
    return results


def get_sjg_jobs(pipelines):
    """Get sjg-lab jobs for all non-skipped pipelines in parallel.

    Returns:
        list of (pipeline_id, job_dict) tuples, ordered by pipeline ID
        descending.
    """
    all_results = []
    total = len(pipelines)
    done = 0

    with concurrent.futures.ThreadPoolExecutor(
            max_workers=NUM_WORKERS) as pool:
        futures = {pool.submit(fetch_pipeline_jobs, pipe): pipe
                   for pipe in pipelines}
        for future in concurrent.futures.as_completed(futures):
            done += 1
            pipe = futures[future]
            tout.progress(
                f'Pipeline {pipe["id"]} ({done}/{total})')
            all_results.extend(future.result())
    tout.clear_progress()

    all_results.sort(key=lambda x: -x[0])
    return all_results


def show_summary(sjg_jobs, num_pipelines, board_filter):
    """Show the board reliability summary table."""
    board_results = defaultdict(list)
    pipeline_ids = set()

    for pid, job in sjg_jobs:
        name = job['name']
        if board_filter and name != board_filter:
            continue
        board_results[name].append((pid, job['status'], job))
        pipeline_ids.add(pid)

    print(f'\nChecked {len(pipeline_ids)} pipelines with sjg-lab jobs '
          f'(out of {num_pipelines} total)\n')

    # Collect all statuses across all boards for column headers
    all_statuses = set()
    board_data = {}
    for board, results in sorted(board_results.items()):
        counts = defaultdict(int)
        for _, s, _ in results:
            counts[s] += 1
        all_statuses.update(counts.keys())
        total = len(results)
        failed = counts.get('failed', 0)
        fail_pct = 100 * failed / total if total else 0
        board_data[board] = (fail_pct, total, counts, results)

    # Order statuses: success first, failed second, then the rest sorted
    status_order = []
    for s in ['success', 'failed']:
        if s in all_statuses:
            status_order.append(s)
            all_statuses.discard(s)
    status_order.extend(sorted(all_statuses))

    # Short labels for column headers
    status_labels = {
        'success': 'Pass', 'failed': 'Fail', 'running': 'Run',
        'pending': 'Pend', 'created': 'Crtd', 'canceled': 'Canc',
        'skipped': 'Skip', 'manual': 'Man',
    }

    summary = []
    for board in sorted(board_data):
        fail_pct, total, counts, results = board_data[board]
        summary.append((fail_pct, board, total, counts, results))
    summary.sort(key=lambda x: (-x[0], x[1]))

    hdr_cols = ''.join(
        f' {status_labels.get(s, s[:4].title()):>5}' for s in status_order)
    print(f'{"Board":<20} {"Runs":>5}{hdr_cols} {"Fail%":>6}')
    print('-' * (33 + 6 * len(status_order)))
    for fail_pct, board, total, counts, results in summary:
        cols = ''.join(
            f' {counts.get(s, 0):>5}' for s in status_order)
        marker = ' ***' if fail_pct > 0 else ''
        print(f'{board:<20} {total:>5}{cols} {fail_pct:>5.1f}%{marker}')

    print()
    for fail_pct, board, total, counts, results in summary:
        if counts.get('failed', 0) > 0:
            fail_pipes = [str(pid) for pid, s, _ in results if s == 'failed']
            print(f'{board}: failed in pipelines {", ".join(fail_pipes)}')

    return summary


def show_detail(sjg_jobs, board_filter):
    """Show failure logs for failed sjg-lab jobs."""
    failed_jobs = [(pid, job) for pid, job in sjg_jobs
                   if job['status'] == 'failed'
                   and (not board_filter or job['name'] == board_filter)]
    if not failed_jobs:
        return

    # Fetch logs in parallel
    def fetch_one(pid_job):
        pid, job = pid_job
        try:
            log = get_job_log(job['id'])
        except Exception as e:
            log = f'  (could not fetch log: {e})'
        return pid, job, log

    done = 0
    total = len(failed_jobs)
    results = []

    with concurrent.futures.ThreadPoolExecutor(
            max_workers=NUM_WORKERS) as pool:
        futures = {pool.submit(fetch_one, pj): pj for pj in failed_jobs}
        for future in concurrent.futures.as_completed(futures):
            done += 1
            pid, job = futures[future]
            tout.progress(
                f'Fetching log for {job["name"]} ({done}/{total})')
            results.append(future.result())
    tout.clear_progress()

    # Print in pipeline-ID order
    results.sort(key=lambda x: -x[0])
    for pid, job, log in results:
        print(f'\n{"=" * 70}')
        print(f'Board: {job["name"]}  Pipeline: {pid}  Job: {job["id"]}')
        print(f'URL: {job["web_url"]}')
        print(f'{"=" * 70}')
        print(log)


def main():
    parser = argparse.ArgumentParser(
        description='Check sjg-lab board reliability')
    parser.add_argument('-d', '--detail', action='store_true',
                        help='show failure logs')
    parser.add_argument('-b', '--board',
                        help='filter to a specific board')
    parser.add_argument('-n', '--num', type=int, default=20,
                        help='number of pipelines to check (default 20)')
    args = parser.parse_args()

    tout.init(tout.INFO)

    tout.progress('Reading pipeline list')
    pipelines = api_get(
        f'/pipelines?per_page={args.num}&order_by=id&sort=desc')
    tout.clear_progress()

    sjg_jobs = get_sjg_jobs(pipelines)
    show_summary(sjg_jobs, len(pipelines), args.board)
    if args.detail:
        show_detail(sjg_jobs, args.board)


if __name__ == '__main__':
    main()
