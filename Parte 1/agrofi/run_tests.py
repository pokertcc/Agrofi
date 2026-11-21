"""
Direct Test Runner for AgroFi
"""
import sys
import traceback
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))

import tests.test_agrofi as t
import tests.test_vault_oracle_bridge as t_vault

tests = [
    ("test_vtn_ingestor", t.test_vtn_ingestor),
    ("test_sicar_ingestor", t.test_sicar_ingestor),
    ("test_srtm_processor", t.test_srtm_processor),
    ("test_sentinel_ndvi_engine", t.test_sentinel_ndvi_engine),
    ("test_valuation_regressor_benchmark", t.test_valuation_regressor_benchmark),
    ("test_risk_engine_ltv_bounds", t.test_risk_engine_ltv_bounds),
    ("test_web3_output_contract", t.test_web3_output_contract),
    ("test_stacking_and_quantiles", t.test_stacking_and_quantiles),
    ("test_monte_carlo_var_distribution", t.test_monte_carlo_var_distribution),
    ("test_oracle_keeper_service", t.test_oracle_keeper_service),
    ("test_oracle_payload_to_solidity_conversion", t_vault.test_oracle_payload_to_solidity_conversion),
]

passed = 0
failed = 0

print("=" * 65)
print("           AGROFI TEST SUITE EXECUTION           ")
print("=" * 65)

for name, test_func in tests:
    try:
        test_func()
        print(f"  [PASS] {name}")
        passed += 1
    except Exception as e:
        print(f"  [FAIL] {name}: {e}")
        traceback.print_exc()
        failed += 1

print("=" * 65)
print(f"TOTAL: {len(tests)} | PASSED: {passed} | FAILED: {failed}")
print("=" * 65)

if failed > 0:
    sys.exit(1)
