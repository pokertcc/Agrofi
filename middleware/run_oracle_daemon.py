import sys
import os

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

import time
import argparse
from middleware.web3_client import AgroFiWeb3Client
from middleware.oracle_service import AgroRiskOracle, AgroRiskData
from middleware.config import ACCOUNTS

SCENARIOS = {
    "optimal": AgroRiskData(
        ndvi=0.82,
        precipitation_deficit=0.05,
        soil_moisture=65.0,
        commodity_price_ratio=1.10
    ),
    "moderate_stress": AgroRiskData(
        ndvi=0.62,
        precipitation_deficit=-0.25,
        soil_moisture=38.0,
        commodity_price_ratio=1.00
    ),
    "severe_drought": AgroRiskData(
        ndvi=0.30,
        precipitation_deficit=-0.70,
        soil_moisture=12.0,
        commodity_price_ratio=0.88
    ),
    "frost": AgroRiskData(
        ndvi=0.45,
        precipitation_deficit=-0.10,
        soil_moisture=45.0,
        commodity_price_ratio=0.92
    )
}

def main():
    parser = argparse.ArgumentParser(description="AgroFi Web3 Oracle & Risk Middleware")
    parser.add_argument("--token-id", type=int, default=1, help="AgroNFT Token ID to monitor")
    parser.add_argument("--scenario", choices=list(SCENARIOS.keys()), default="optimal", help="Agro risk scenario")
    parser.add_argument("--loop", action="store_true", help="Run in continuous monitoring loop")
    parser.add_argument("--interval", type=int, default=10, help="Loop interval in seconds")

    args = parser.parse_args()

    print("[AgroFi] Starting Web3 Oracle Middleware...")
    client = AgroFiWeb3Client()
    oracle = AgroRiskOracle(client)

    if not args.loop:
        data = SCENARIOS[args.scenario]
        print(f"Injecting scenario: '{args.scenario}' for Token ID #{args.token_id}")
        oracle.push_risk_update(args.token_id, data)
    else:
        print(f"Running continuous monitoring for Token ID #{args.token_id} (Interval: {args.interval}s)")
        scenarios_cycle = ["optimal", "moderate_stress", "severe_drought"]
        idx = 0
        while True:
            scenario_name = scenarios_cycle[idx % len(scenarios_cycle)]
            data = SCENARIOS[scenario_name]
            print(f"\n[{time.strftime('%X')}] Applying cycle scenario: '{scenario_name}'")
            oracle.push_risk_update(args.token_id, data)
            idx += 1
            time.sleep(args.interval)

if __name__ == "__main__":
    main()
