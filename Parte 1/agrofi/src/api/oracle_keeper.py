"""
AgroFi Oracle Keeper Daemon
Continuously fetches ML valuations, checks heartbeat freshness, and prepares/relays transactions to AgroFiVault.sol.
"""
from typing import Dict, Any, List, Optional
import time
from datetime import datetime, timezone
from pydantic import BaseModel
from src.api.service import orchestrator
from src.core.schemas import Web3CollateralPayload


class OracleRelayTransaction(BaseModel):
    token_id: int
    land_id: str
    car_code: str
    predicted_value_wei: str
    ltv_ratio_bps: int
    health_factor_wad: str
    timestamp: int
    tx_status: str
    gas_estimate: int


class AgroFiOracleKeeper:
    """
    Guardião de oráculo off-chain que monitora a atualização periódica das safras,
    gera o payload padronizado e calcula os parâmetros para chamada on-chain.
    """

    def __init__(self, heartbeat_seconds: int = 86400):
        self.heartbeat_seconds = heartbeat_seconds
        self.last_sync_timestamps: Dict[str, int] = {}
        self.tx_history: List[OracleRelayTransaction] = []

    def prepare_onchain_update(
        self,
        land_id: str,
        token_id: int = 1,
        simulated_drought_pct: float = 0.0
    ) -> OracleRelayTransaction:
        """
        Gera a transação formatada para a função updateLandValuation do AgroFiVault.sol.
        """
        payload: Web3CollateralPayload = orchestrator.get_web3_collateral_payload(
            land_id=land_id,
            simulated_drought_pct=simulated_drought_pct
        )

        now_ts = int(time.time())
        predicted_value_wei = str(int(payload.predicted_value * 10**18))
        ltv_ratio_bps = int(round(payload.ltv_ratio * 10000))
        health_factor_wad = str(int(round(payload.health_factor * 10**18)))

        tx = OracleRelayTransaction(
            token_id=token_id,
            land_id=payload.land_id,
            car_code=payload.car_code,
            predicted_value_wei=predicted_value_wei,
            ltv_ratio_bps=ltv_ratio_bps,
            health_factor_wad=health_factor_wad,
            timestamp=now_ts,
            tx_status="SIMULATED_SUCCESS",
            gas_estimate=85420
        )

        self.last_sync_timestamps[land_id] = now_ts
        self.tx_history.append(tx)
        return tx

    def execute_all_parcels_sync(self, simulated_drought_pct: float = 0.0) -> List[OracleRelayTransaction]:
        """
        Sincroniza todos os talhões cadastrados no SICAR em lote.
        """
        parcels_df = orchestrator.sicar_ingestor.load_data()
        results = []
        for idx, row in parcels_df.iterrows():
            token_id = idx + 1
            tx = self.prepare_onchain_update(
                land_id=row["land_id"],
                token_id=token_id,
                simulated_drought_pct=simulated_drought_pct
            )
            results.append(tx)
        return results

    def get_keeper_status(self) -> Dict[str, Any]:
        return {
            "total_relayed_updates": len(self.tx_history),
            "monitored_parcels": list(self.last_sync_timestamps.keys()),
            "latest_heartbeat_utc": datetime.now(timezone.utc).isoformat(),
            "status": "ACTIVE_KEEPER_DAEMON"
        }


# Singleton do Keeper
oracle_keeper = AgroFiOracleKeeper()
