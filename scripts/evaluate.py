"""Reproducible fixture smoke evaluation, never a production quality benchmark."""
import json
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from qc.media import create_fixtures
from qc.engine import run_inspection, shot_set_f1


if __name__ == '__main__':
    metas=create_fixtures(ROOT/'data'/'fixtures')
    rows=[]
    for meta in metas:
        report=run_inspection(meta,ROOT/'data'/'fixtures'/meta['video_id']/'video.mp4',
                              ROOT/'data'/'evaluation'/meta['video_id'])
        predicted=[f['shot_id'] for f in report['findings'] if f['zone']=='confirmed']
        rows.append({'fixture':meta['video_id'], 'predicted':predicted,
                     'gold':meta['expected_defect_shots'], 'shot_set_f1':shot_set_f1(predicted,meta['expected_defect_shots']),
                     'elapsed_sec':report['elapsed_sec'], 'tokens':report['tokens']})
    result={'scope':'3 controlled synthetic fixtures; regression smoke check only; NOT production accuracy',
            'rows':rows,'macro_f1':sum(r['shot_set_f1'] for r in rows)/len(rows)}
    output=ROOT/'data'/'evaluation'/'summary.json'
    output.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False,indent=2))
