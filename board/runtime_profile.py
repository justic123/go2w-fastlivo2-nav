"""Resolve supported native profiles without silently changing sensor calibration."""
from fusion_backend import plan


def settings(config):
    backend = plan(config)
    hz = config.get('image_hz', 5)
    threads = config.get('omp_threads', 4)
    if not backend['vision']:
        hz = 0
    elif type(hz) is not int or hz not in (5, 10):
        raise ValueError('Installed image_hz must be 5 or 10')
    if type(threads) is not int or threads not in (1, 2, 4):
        raise ValueError('Installed omp_threads must be 1, 2 or 4')
    return dict(image_hz=hz, decoder_mode=f'{hz}hz' if hz else None, env=dict(
        OMP_THREAD_LIMIT=str(threads), OMP_NUM_THREADS=str(threads),
        OMP_WAIT_POLICY='PASSIVE', OPENBLAS_NUM_THREADS='1',
        GO2W_IMAGE_PROFILE=f'{hz}hz' if hz else 'disabled'))
