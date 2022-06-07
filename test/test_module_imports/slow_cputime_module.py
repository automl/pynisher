"""Keeps cpu busy for `sleep` seconds"""
import time

sleep = 10

start = time.perf_counter()
while True:
    duration = time.perf_counter() - start
    if duration > sleep:
        break
