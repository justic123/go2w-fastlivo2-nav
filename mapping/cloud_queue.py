"""Bounded latest-cloud policy. Never use this for IMU samples."""
import queue

def offer_latest(q, item):
 dropped=0
 while True:
  try:q.put_nowait(item);return dropped
  except queue.Full:
   try:q.get_nowait();dropped+=1
   except queue.Empty:pass

def stale_cloud(now,stamp,max_age=.5):
 return now-stamp>max_age
