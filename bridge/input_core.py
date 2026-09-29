"""Pure conversion primitives. Time assumptions are explicit, never inferred."""
import numpy as np
EXPECTED={('x',7,0,1),('y',7,4,1),('z',7,8,1),('intensity',7,12,1),('ring',4,16,1),('time',7,18,1)}
RAW=np.dtype({'names':['x','y','z','intensity','ring','time'],'formats':['<f4','<f4','<f4','<f4','<u2','<f4'],'offsets':[0,4,8,12,16,18],'itemsize':22})
OUT=np.dtype({'names':['x','y','z','intensity','ring','timestamp'],'formats':['<f4','<f4','<f4','<f4','<u2','<f8'],'offsets':[0,4,8,12,16,18],'itemsize':26})
def convert_cloud(meta,payload,unit,reference):
 if unit!='ns' or reference not in ('start','end'):raise ValueError('Explicit supported timing hypothesis required')
 if {tuple(f) for f in meta['fields']}!=EXPECTED or meta['bigendian'] or meta['point_step']!=22 or meta['height']!=1:raise ValueError('Unsupported point schema')
 n=meta['width']
 if n<2 or len(payload)!=n*22 or meta['row_step']!=n*22:raise ValueError('Malformed cloud dimensions')
 a=np.frombuffer(payload,dtype=RAW,count=n)
 raw_times=a['time'][np.isfinite(a['time']) & (a['time']>=0)]
 if not len(raw_times):raise ValueError('No finite nonnegative point time')
 scan_span=float(raw_times.max())*1e-9
 if scan_span>.2:raise ValueError('Scan exceeds diagnostic 200ms bound')
 valid=a['ring']<16
 for k in ['x','y','z','intensity','time']:valid &= np.isfinite(a[k])
 valid &= a['time']>=0
 a=a[valid]
 if len(a)<2:raise ValueError('Too few valid points')
 a=a[np.argsort(a['time'],kind='stable')]
 offsets=a['time'].astype(float)*1e-9
 if offsets[-1]>.2:raise ValueError('Scan exceeds diagnostic 200ms bound')
 header=float(meta['stamp_sec'])+meta['stamp_nanosec']*1e-9
 start=header-(scan_span if reference=='end' else 0)
 b=np.empty(len(a),dtype=OUT)
 for k in ['x','y','z','intensity','ring']:b[k]=a[k]
 b['timestamp']=start+offsets
 # FAST-LIVO2 normalizes its curvature to the first retained point.
 return b,float(b['timestamp'][0]),float(b['timestamp'][-1]),int(n-len(a))

class TickClock:
 """1ms tick, frozen median receipt anchor after warmup. Not hardware sync."""
 def __init__(self,warmup=500):
  self.warmup=warmup;self.first=None;self.last=None;self.anchor=None;self.samples=[];self.duplicates=0
 def observe(self,tick,receipt):
  if self.last is not None:
   if tick==self.last:self.duplicates+=1;return None
   if tick<self.last:raise ValueError('Tick reset/wrap: stop and reinitialize explicitly')
  self.last=tick
  if self.first is None:self.first=tick
  relative=(tick-self.first)*.001
  if self.anchor is None:
   self.samples.append(receipt-relative)
   if len(self.samples)>=self.warmup:self.anchor=float(np.median(self.samples))
   else:return None
  return self.anchor+relative
