"""Apply replay subsampling once; native acquisition already owns its rate."""
class ImageSampler:
    def __init__(self, mode, source_rate_limited=False):
        if mode not in ('5hz', '10hz'):raise ValueError('Expected 5hz or 10hz')
        self.interval=.2 if mode=='5hz' and not source_rate_limited else 0.
        self.next_stamp=None

    def accept(self, stamp):
        if self.interval and self.next_stamp is not None and stamp<self.next_stamp-.005:
            return False
        if self.interval:
            if self.next_stamp is None:self.next_stamp=stamp
            while self.next_stamp<=stamp+.005:self.next_stamp+=self.interval
        return True
