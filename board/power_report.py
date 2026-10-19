#!/usr/bin/env python3
"""Compare isolated power-mode replays; does not connect to or change the robot."""
import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re

from analyze import compare, describe


def load(path):
    return json.loads(path.read_text())


def summarize(root, relative, mode, threads):
    folder = root / relative
    summary = load(folder / 'balanced10/summary.json')
    run = summary['run']
    log = (folder / 'balanced10-tegrastats.log').read_text()
    power_path = folder / 'root-tegrastats.log'
    power_log = power_path.read_text() if power_path.exists() else ''
    # The privileged monitor can outlive replay cleanup. Exclude subsequent idle samples.
    def timestamp(line):
        try:
            return datetime.strptime(line[:19], '%m-%d-%Y %H:%M:%S')
        except ValueError:
            return None
    logged_times = [stamp for line in log.splitlines() if (stamp := timestamp(line)) is not None]
    all_power_lines = power_log.splitlines()
    if logged_times:
        power_log = '\n'.join(line for line in all_power_lines
                              if (stamp := timestamp(line)) is not None
                              and logged_times[0] <= stamp <= logged_times[-1])
    rss = [int(sample['rss'].split()[1]) / 1024 for sample in run['samples']]
    temperature = [float(value) for value in re.findall(r'CPU@([0-9.]+)C', log)]
    frequency = [int(value) for value in re.findall(r'\d+%@([0-9]+)', log)]
    power = [int(value) / 1000 for value in re.findall(r'VDD_IN (\d+)mW/', power_log)]
    lag = summary['metrics']['processing_lag_s']
    return dict(case=relative, mode=mode, threads=threads, input_seconds=run['seconds'],
                error=run['error'], processing_lag_s=lag,
                final_processing_lag_s=run['final_profile']['metrics']['processing_lag_s'],
                odom_hz=(summary['odom_count'] - 1) / summary['source_duration_s'],
                max_algorithm_rss_mib=max(rss) if rss else None,
                cpu_temperature_c=describe(temperature),
                sampled_cpu_frequency_mhz=describe(frequency),
                sampled_module_input_power_w=describe(power),
                power_samples_before_window_filter=sum('VDD_IN ' in line for line in all_power_lines),
                power_measurement_note='VDD_IN sensor samples only; may cover a partial window, excludes robot motors and peripherals.',
                lio_ms=summary['stages_ms'].get('lio_full'),
                vio_ms=summary['stages_ms'].get('vio_full'),
                within_0_6s_offline_reference=run['error'] is None and lag['max'] <= .6,
                parameters_sha256=hashlib.sha256((folder / 'balanced10/parameters.yaml').read_bytes()).hexdigest(),
                navigation_tested=False, ground_truth_accuracy_tested=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('evidence', type=Path)
    args = parser.parse_args()
    cases = [('long-15w', '15W', 2), ('maxn-t2', 'MAXN', 2), ('maxn-t4', 'MAXN', 4)]
    records = [summarize(args.evidence, *case) for case in cases
               if (args.evidence / case[0] / 'balanced10/summary.json').exists()]
    agreement = {}
    baseline = args.evidence / 'long-15w/balanced10'
    if baseline.exists():
        for record in records:
            if record['case'] == 'long-15w':
                continue
            agreement[record['case']] = compare(baseline, args.evidence / record['case'] / 'balanced10')
    report = dict(date='2026-10-15', device='Go2W Orin NX 16GB', cases=records,
                  agreement_with_15w=agreement,
                  notes=['All cases use the same 530-second recorded sensor input and balanced10 spatial parameters.',
                         'The 0.6s reference is an offline screen, not navigation safety certification.',
                         'Agreement between estimates is not independent ground-truth accuracy.',
                         'No jetson_clocks lock or thermal protection changes were applied.'])
    tail_path = args.evidence / 'bag_tail_530s.json'
    if tail_path.exists():
        tail = load(tail_path)
        report['bag_tail_audit'] = tail
        report['notes'].append('The bag has images/IMU beyond final cloud coverage. Original EOF return codes and cached profile ages alone do not prove backlog or complete drainage.')
        for record in records:
            run = load(args.evidence / record['case'] / 'balanced10/run.json')
            final_stamp = run['final_profile']['metrics']['state_stamp']
            record['final_state_stamp'] = final_stamp
            record['last_supported_image_stamp'] = tail['last_supported_image_stamp']
            record['last_supported_image_processed'] = abs(final_stamp - tail['last_supported_image_stamp']) < 1e-4
            record['within_0_6s_offline_reference'] = (record['processing_lag_s']['max'] <= .6
                                                     and record['last_supported_image_processed'])
    (args.evidence / 'power_comparison.json').write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
