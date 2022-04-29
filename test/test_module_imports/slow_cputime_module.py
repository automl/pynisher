"""Keeps cpu busy for `sleep` seconds"""
import time

sleep = 10

start = time.process_time()
while True:
    duration = time.process_time() - start
    if duration > sleep:
        break
