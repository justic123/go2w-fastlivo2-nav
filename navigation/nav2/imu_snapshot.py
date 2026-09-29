"""Choose a genuinely received, nonfuture sample without retimestamping it."""
def select_snapshot(records, history, now, fault):
 eligible=[r for r in records if r['stamp']<=now and r['receipt']<=now]
 if not eligible:return None
 return dict(eligible[-1],fault=fault,history=[s for s in history if s[0]<=now])
