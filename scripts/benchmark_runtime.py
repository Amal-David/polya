#!/usr/bin/env python3
"""Bounded, correctness-checked runtime experiment; no claimed universal speedup."""
from __future__ import annotations
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import statistics
import subprocess
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from polya.automata import Machine, prepare_machine, simulate
from polya.runtime import inspect_runtime


def measure(function, repeats):
    samples = []
    for _ in range(repeats):
        start = time.perf_counter_ns()
        function()
        samples.append((time.perf_counter_ns() - start) / 1e6)
    return {'samples_ms': samples, 'median_ms': statistics.median(samples)}


def benchmark(repeats=5, words=2000, threads=1):
    if not 1 <= repeats <= 20 or not 1 <= words <= 20000 or not 1 <= threads <= 16:
        raise ValueError('repeats must be 1..20, words 1..20000, threads 1..16')
    states = [f'q{i}' for i in range(200)]
    machine = Machine(kind='mealy', states=states, initial='q0', alphabet=[0, 1],
                      transitions=[{'source': state, 'symbol': symbol,
                                    'target': states[(index + symbol + 1) % 200], 'output': str(index % 3)}
                                   for index, state in enumerate(states) for symbol in [0, 1]])
    prepare_start = time.perf_counter_ns()
    prepared = prepare_machine(machine)
    preparation_ms = (time.perf_counter_ns() - prepare_start) / 1e6
    word = [0, 1] * 12
    expected = simulate(machine, word)
    assert prepared.replay(word) == expected
    def reference():
        for _ in range(words):
            assert simulate(machine, word) == expected
    def repeated():
        for _ in range(words):
            assert prepared.replay(word) == expected
    result = {'runtime': inspect_runtime(), 'word_count': words, 'word_length': len(word),
              'state_count': len(states), 'preparation_ms': preparation_ms,
              'reference': measure(reference, repeats), 'prepared': measure(repeated, repeats)}
    if threads > 1:
        # Bounded input and work chunks amortize scheduling; no shared iterator.
        sizes = [words // threads + (i < words % threads) for i in range(threads)]
        def chunk(count):
            for _ in range(count):
                assert prepared.replay(word) == expected
        def threaded():
            with ThreadPoolExecutor(max_workers=threads) as pool:
                list(pool.map(chunk, sizes))
        result['threaded'] = measure(threaded, repeats)
        result['threads'] = threads
    command = [sys.executable, '-m', 'polya', 'find', 'constraints']
    def cold_start():
        completed = subprocess.run(command, cwd=Path(__file__).resolve().parents[1],
                                   capture_output=True, timeout=30, check=True)
        assert json.loads(completed.stdout)
    result['cold_cli'] = measure(cold_start, repeats)
    result['scope'] = ('Same-interpreter replay comparison. Prepared validation is measured separately. '
                       'Not Python-version, JIT, Rust, real-puzzle or AI-agent speedup evidence. '
                       'Thread timing includes pool creation; standard builds may gain nothing.')
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--repeats', type=int, default=5)
    parser.add_argument('--words', type=int, default=2000)
    parser.add_argument('--threads', type=int, default=1)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--profile', type=Path)
    args = parser.parse_args()
    if args.profile:
        # Python 3.15's relocated deterministic profiler, with an older fallback.
        if sys.version_info >= (3, 15):
            from profiling import tracing
        else:
            import cProfile as tracing
        profiler = tracing.Profile()
        result = profiler.runcall(benchmark, args.repeats, args.words, args.threads)
        profiler.dump_stats(str(args.profile))
        result['instrumented'] = True
    else:
        result = benchmark(args.repeats, args.words, args.threads)
        result['instrumented'] = False
    text = json.dumps(result, ensure_ascii=True, indent=2, allow_nan=False)
    if args.output:
        args.output.write_text(text + '\n', encoding='utf-8')
    else:
        print(text)


if __name__ == '__main__':
    main()
