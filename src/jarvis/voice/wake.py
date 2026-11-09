"""Experimental score gate only. No microphone, model download or auto-start."""
import math
import time


class WakeGate:
    def __init__(self, threshold=.7, cooldown=5, clock=time.monotonic):
        self.threshold = threshold
        self.cooldown = cooldown
        self.clock = clock
        self.enabled = False
        self.last = float('-inf')
        self.hits = 0

    def disable(self):
        self.enabled = False
        self.hits = 0

    def feed(self, score, *, idle=True):
        if not self.enabled or not idle or not math.isfinite(score) or score < self.threshold:
            self.hits = 0
            return False
        self.hits += 1
        if self.hits < 3 or self.clock() - self.last < self.cooldown:
            return False
        self.last = self.clock()
        self.hits = 0
        return True
