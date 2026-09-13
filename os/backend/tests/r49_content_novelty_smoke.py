"""Network-free novelty gate regression and negative controls."""
import sys
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
