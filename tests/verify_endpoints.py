import urllib.request
import json

base = 'http://127.0.0.1:8000'

def check(url, method='GET', data=None):
    req = urllib.request.Request(base + url, method=method)
    if data:
        req.add_header('Content-Type', 'application/json')
        body = json.dumps(data).encode('utf-8')
    else:
        body = None
    with urllib.request.urlopen(req, data=body, timeout=10) as resp:
        res = json.loads(resp.read().decode('utf-8'))
        print(f"[{method} {url}] -> {resp.status} OK")
        return res

check('/health')
presets = check('/api/sandbox/presets')
print(f"Presets count: {len(presets.get('presets', {}))}")
autonomy = check('/api/sandbox/autonomy')
print(f"Autonomy level: {autonomy.get('current_level')}")
readiness = check('/api/sandbox/readiness')
print(f"Readiness total score: {readiness.get('total_score')} / 100")
ks = check('/api/sandbox/kill-switch')
print(f"Kill switch active: {ks.get('is_active')}")

# Test Preset A Single Event
run_res = check('/api/sandbox/run', method='POST', data={'preset_id': 'PRESET_A_TRANSIENT_UPI'})
print(f"Single Event Decision: {run_res.get('governor_decision', {}).get('selected_action')} / {run_res.get('governor_decision', {}).get('decision')}")

# Test What-If
wi_res = check('/api/sandbox/what-if', method='POST', data={'payment_id': run_res['payment']['payment_id']})
print(f"What-If dynamic candidates count: {wi_res.get('total_candidate_actions_evaluated')} actions evaluated dynamically")

# Test Counterfactual Replay
replay_res = check(f"/api/sandbox/replay/{run_res['payment']['payment_id']}")
print(f"Actual action: {replay_res.get('actual_path', {}).get('action_taken')}, counterfactual count: {len(replay_res.get('counterfactual_paths', []))}")

# Test Portfolio Simulation (100 events)
portfolio_res = check('/api/sandbox/portfolio', method='POST', data={'population_size': 100, 'seed': 42})
print(f"Portfolio simulation strategies: {list(portfolio_res.get('results', {}).keys())}")
print(f"Governor net recovery: {portfolio_res['results']['GOVERNOR']['net_recovery']}")

print("\n>>> ALL API VERIFICATIONS 100% PASSED SUCCESSFULLY! <<<")
