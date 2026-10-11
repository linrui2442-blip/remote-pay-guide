"""Network-free novelty gate regression and negative controls."""
import sys
import json, os, sqlite3, tempfile, uuid
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "video-factory"))
from content_novelty import compare

historical=[
 {"content_id":"short11","video_subject":"How to Give a Client the Correct USDT Address (TRC20 vs ERC20)","video_script":"Confirm the receiving platform supports USDT network. Choose the matching network, copy the receiving address, consider a small test transfer, and never share a seed phrase or private key."},
 {"content_id":"short12","video_subject":"Which USDT Network Should a Client Use?","video_script":"Check the official receive screen, choose a network both sides support, send the network name and receiving address, compare before sending, and never share a seed phrase or private key."},
]
r=compare(historical[1]["video_subject"],historical[1]["video_script"],historical); assert r["decision"]=="BLOCK",r
a=compare("USDT vs USDC for client payments","Compare asset choice, issuer and token differences, client acceptance, and receiving compatibility.",historical); assert a["decision"]=="PASS",a
b=compare("How to verify a stablecoin payment arrived","Check transaction status, confirmations, wallet or exchange balance, and the transaction hash.",historical); assert b["decision"]=="PASS",b
print("Content novelty gate smoke passed")

# Canonical produced plans supplement legacy JSONL history, while an
# unproduced preview and the candidate itself never become comparison rows.
ROOT=Path(__file__).resolve().parents[3]
db=Path(tempfile.gettempdir())/('novelty-history-'+uuid.uuid4().hex+'.db')
os.environ['OS_TESTING']='1'; os.environ['OS_DATABASE_PATH']=str(db)
sys.path.insert(0,str(ROOT/'os'/'backend'))
conn=sqlite3.connect(db)
conn.execute('CREATE TABLE intelligence_content_plans(id INTEGER PRIMARY KEY, content_id TEXT, status TEXT, payload_json TEXT)')
conn.execute('CREATE TABLE production_results(id INTEGER PRIMARY KEY, video_id TEXT, status TEXT)')
payload={'topic':'Canonical payment topic','angle':'Canonical angle','hook':'Hook','script':'Script','cta':'CTA'}
conn.execute('INSERT INTO intelligence_content_plans VALUES(1,?,?,?)',('canonical-produced','materialized',json.dumps(payload)))
conn.execute('INSERT INTO production_results VALUES(1,?,?)',('canonical-produced','completed'))
conn.execute('INSERT INTO intelligence_content_plans VALUES(2,?,?,?)',('preview-only','preview',json.dumps(payload)))
conn.commit(); conn.close()
from intelligence.novelty import novelty_history, bounded_creative_history
rows=novelty_history('candidate-id'); ids={row['content_id'] for row in rows}
assert 'canonical-produced' in ids and 'preview-only' not in ids
assert len(ids)==len(rows)
assert 'canonical-produced' not in {row['content_id'] for row in novelty_history('canonical-produced')}
creative=bounded_creative_history('candidate-id')
canonical=next(row for row in creative if row['content_id']=='canonical-produced')
assert canonical == {'content_id':'canonical-produced','topic':'Canonical payment topic','angle':'Canonical angle','hook':'Hook','visual_direction':''}
assert len(creative) <= 20 and creative == bounded_creative_history('candidate-id')
assert 'canonical-produced' not in {row['content_id'] for row in bounded_creative_history('canonical-produced')}
assert all(set(row)=={'content_id','topic','angle','hook','visual_direction'} for row in creative)
print('CANONICAL_PRODUCTION_NOVELTY_HISTORY=PASS')
print('NOVELTY_SELF_COMPARISON_EXCLUDED=PASS')
print('BOUNDED_CREATIVE_HISTORY=PASS')
db.unlink(missing_ok=True)
