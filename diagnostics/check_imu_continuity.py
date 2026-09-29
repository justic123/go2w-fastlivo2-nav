#!/usr/bin/env python3
"""Conservative input-quality gate, not a localization accuracy assessment."""
import csv,json,sys
from pathlib import Path
path=Path(sys.argv[1]);output=Path(sys.argv[2]);limit_ms=20
rows=list(csv.DictReader(path.open()));ticks=[int(r['tick']) for r in rows];gaps=[b-a for a,b in zip(ticks,ticks[1:])]
result={'criterion':'Conservative diagnostic: at least 500 rows, no tick rollback, no sample gap >20ms; not an accuracy guarantee','rows':len(rows),'max_tick_gap_ms':max(gaps) if gaps else None,'duplicate_ticks':sum(x==0 for x in gaps),'backwards_ticks':sum(x<0 for x in gaps),'gaps_over_20ms':sum(x>limit_ms for x in gaps)}
result['pass']=len(rows)>=500 and bool(gaps) and min(gaps)>=0 and max(gaps)<=limit_ms
output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
sys.exit(0 if result['pass'] else 1)
