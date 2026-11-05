from pathlib import Path
import csv, json, re, hashlib
base=Path('.cache/tests/spu-sha256')
rows=[]; hashes={}
fields=['scope','tool','configuration','key_bits','direction','receiver_mbit_s','seconds','udp_target','lost_packets','packets','loss_percent','status','source_log']
def records(name, pattern, ctx, marker=None, allow_partial=False):
 p=base/name; s=p.read_text(); hashes[name]=hashlib.sha256(p.read_bytes()).hexdigest()
 if marker and marker not in s: raise ValueError(f'Missing cleanup pass: {name}')
 for m in re.finditer(pattern,s):
  r={k:'' for k in fields};r.update(ctx);r['source_log']=name
  groups=m.groupdict();r.update({k:v for k,v in groups.items() if k in fields})
  try:
   start=s.index('{',m.end());j,_=json.JSONDecoder().raw_decode(s[start:])
   if j.get('error'): raise ValueError(j['error'])
   end=j['end'];v=end.get('sum_received',end.get('sum',{}))
   r['receiver_mbit_s']=f"{v['bits_per_second']/1e6:.2f}";r['seconds']=f"{v['seconds']:.3f}"
   for k in ['lost_packets','packets']:r[k]=v.get(k,'')
   r['loss_percent']=v.get('lost_percent','');r.setdefault('status','complete')
   if not r['status']:r['status']='complete'
  except (ValueError,KeyError) as e:
   if not allow_partial:raise
   r['status']='incomplete_pair_restart_observed'
  rows.append(r)
core=[('round2-stock-generic.log','cbc_sha256_generic_rps3','plain_generic'),('round2-stock-arm.log','cbc_sha256_arm_rps3','both_asm'),('round2-stock-gcm.log','aes_gcm_arm_rps3','gcm_asm')]
pattern=r'BENCHMARK \w+ AES(?P<key_bits>128|192|256) (?P<direction>forward|reverse)'
for name,config,phase in core:records(name,pattern,dict(scope='same_modem_namespaces',tool='upstream_3.18',configuration=config),f'PHASE_PASS {phase}')
for name,config,tool in [('round2-wireguard-local.log','wireguard_rps3','vendor_3.1.4'),('round2-wireguard-local-rps0.log','wireguard_rps0','vendor_3.1.4'),('round2-stock-wireguard.log','wireguard_rps3','upstream_3.18')]:
 records(name,r'LOCAL_WG_BENCH (?P<direction>forward|reverse)',dict(scope='same_modem_namespaces',tool=tool,configuration=config,key_bits=256),'LOCAL_WIREGUARD_PASS')
for name,pat,config,tool,marker in [('round2-stock-udp-control.log',r'UDP_CONTROL (?P<udp_target>\w+) (?P<direction>forward|reverse)','udp_no_vpn_rps3','upstream_3.18','UDP_CONTROL_PASS'),('round2-stock-wireguard.log',r'LOCAL_WG_UDP (?P<udp_target>\w+) (?P<direction>forward|reverse)','wireguard_udp_rps3','upstream_3.18','LOCAL_WIREGUARD_PASS'),('round2-wireguard-udp.log',r'LOCAL_WG_UDP (?P<udp_target>\w+) (?P<direction>forward|reverse)','wireguard_udp_rps3','vendor_3.1.4','LOCAL_WIREGUARD_PASS'),('round2-udp-control-rps0.log',r'UDP_CONTROL (?P<udp_target>\w+) (?P<direction>forward|reverse)','udp_no_vpn_rps0','vendor_3.1.4','UDP_CONTROL_PASS'),('round2-udp-control-rps3.log',r'UDP_CONTROL (?P<udp_target>\w+) (?P<direction>forward|reverse)','udp_no_vpn_rps3','vendor_3.1.4','UDP_CONTROL_PASS')]:
 records(name,pat,dict(scope='same_modem_namespaces',tool=tool,configuration=config),marker)
for name,config in [('round2-arm-auto.log','arm_auto_rps0'),('round2-arm-split01.log','arm_cpu_server0_client1'),('round2-arm-split10.log','arm_cpu_server1_client0'),('round2-arm-same00.log','arm_cpu_both0'),('round2-arm-mss1200.log','arm_mss1200'),('round2-arm-mss536.log','arm_mss536'),('round2-arm-rps3-long.log','arm_rps3_10s')]:
 records(name,pattern,dict(scope='same_modem_namespaces',tool='vendor_3.1.4',configuration=config),'PHASE_PASS both_asm')
records('round2-hybrid-copy-rx-pool64.log',pattern,dict(scope='same_modem_namespaces',tool='vendor_3.1.4',configuration='quarantined_hybrid_pool_fallback',status='complete_with_expired_replay_window_drops'),'PHASE_PASS hybrid_pool_asm')
records('round2-hybrid-copy-window256.log',pattern,dict(scope='same_modem_namespaces',tool='vendor_3.1.4',configuration='quarantined_hybrid_window256',status='incomplete_pair_restart_observed'),allow_partial=True)
for name,config in [('round2-stock-external-wg1420.log','wireguard_mtu1420'),('round2-stock-external-wg1280.log','wireguard_mtu1280'),('round2-stock-external-wg-offloads.log','wireguard_veth_offloads_off')]:
 records(name,r'EXTERNAL_WG_BENCH (?P<direction>forward|reverse)',dict(scope='external_docker_peer',tool='upstream_3.18',configuration=config,key_bits=256),'EXTERNAL_WIREGUARD_PASS')
for name in ['round2-external-ipsec128.log','round2-external-ipsec256-rps3.log','round2-external-ipsec128-rps3.log']:
 records(name,r'EXTERNAL_ESP_BENCH AES(?P<key_bits>128|256) (?P<direction>forward|reverse)',dict(scope='external_docker_peer',tool='upstream_3.18',configuration='cbc_sha256_arm_'+('rps3' if 'rps3' in name else 'rps0'),status='traffic_complete_normal_unload_retried'))
for name,direction in [('round2-external-plain-peer-forward.log','reverse'),('round2-external-plain-peer-reverse.log','forward')]:
 p=base/name;j=json.loads(p.read_text());hashes[name]=hashlib.sha256(p.read_bytes()).hexdigest();v=j['end']['sum_received'];r={k:'' for k in fields};r.update(scope='external_docker_peer',tool='upstream_3.18',configuration='plain_tcp_peer_as_client',direction=direction,receiver_mbit_s=f"{v['bits_per_second']/1e6:.2f}",seconds=f"{v['seconds']:.3f}",status='complete',source_log=name);rows.append(r)
out=Path('experiments/spu-sha256/round2-results.csv')
with out.open('w',newline='') as f:
 w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
Path('experiments/spu-sha256/round2-logs.sha256').write_text(''.join(f'{h}  {n}\n' for n,h in sorted(hashes.items())))
print(f'{len(rows)} measurements from {len(hashes)} logs recorded')
