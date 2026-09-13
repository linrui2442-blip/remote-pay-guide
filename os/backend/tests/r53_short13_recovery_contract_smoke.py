import json,sys,tempfile
from pathlib import Path
sys.path.insert(0,'video-factory')
from visual_provenance import extract_material_provenance
root=Path(tempfile.mkdtemp()); task=root/'task'; task.mkdir()
sources=[{'provider':'pexels','asset_id':str(i),'source_page':f'https://pexels.com/video/{i}','local_file':f'clip{i}.mp4','search_term':'term'} for i in range(8)]
(task/'script.json').write_text(json.dumps({'material_sources':sources}))
r=extract_material_provenance(task); assert len(r['materials'])==8; assert r['materials'][0]['source_id']=='0'; assert 'final_output' not in r
print('Short13 recovery provenance contract passed')
