"""Bound nonblocking callback servicing before using feedback for control."""
def drain_ready(spin_once, monotonic, max_callbacks=32, budget=.015):
    start=monotonic();count=0
    while count<max_callbacks and monotonic()-start<budget:
        spin_once();count+=1
    return count
