"""
AgroFi Vault & Oracle Payload Serialization Verification Test
Simulates the off-chain Oracle relay pushing Web3CollateralPayload into AgroFiVault.sol
"""
try:
    import pytest
except ImportError:
    pytest = None
from src.core.schemas import Web3CollateralPayload
from src.api.service import orchestrator


def test_oracle_payload_to_solidity_conversion():
    """
    Verifica se o payload gerado pela API Python mapeia com precisão cirúrgica
    para os tipos e unidades exigidos pelo AgroFiVault.sol:
    - landId: string
    - carCode: string
    - predictedValue: uint256 (escalado para 18 decimais)
    - ltvRatioBps: uint256 (3500 a 6500 bps)
    - healthFactor: uint256 (escalado com 1e18)
    """
    payload = orchestrator.get_web3_collateral_payload("TALHAO-MT-001", simulated_drought_pct=0.0)
    
    # 1. Validação de String
    solidity_land_id = payload.land_id
    solidity_car_code = payload.car_code
    assert isinstance(solidity_land_id, str) and len(solidity_land_id) > 0
    assert isinstance(solidity_car_code, str) and len(solidity_car_code) > 0

    # 2. Conversão de Valor Patrimonial (R$ float -> uint256 wei / 18 decimals)
    # Ex: R$ 94,571,288.00 -> 94571288 * 10^18
    solidity_predicted_value = int(payload.predicted_value * 10**18)
    assert solidity_predicted_value > 0

    # 3. Conversão de LTV Ratio (0.35 - 0.65 float -> uint256 basis points: 3500 - 6500)
    solidity_ltv_bps = int(round(payload.ltv_ratio * 10000))
    assert 3500 <= solidity_ltv_bps <= 6500, f"LTV BPS {solidity_ltv_bps} fora da margem segura [3500, 6500]"

    # 4. Conversão do Health Factor (float -> uint256 com precisão 1e18)
    solidity_health_factor = int(round(payload.health_factor * 10**18))
    assert solidity_health_factor > 0

    # 5. Verificação sob Estresse de Seca Severa (-50% NDVI)
    stressed_payload = orchestrator.get_web3_collateral_payload("TALHAO-MT-001", simulated_drought_pct=-50.0)
    stressed_ltv_bps = int(round(stressed_payload.ltv_ratio * 10000))
    stressed_hf = int(round(stressed_payload.health_factor * 10**18))

    # O LTV deve contrair, mas respeitar o piso de 3500 bps (35%)
    assert 3500 <= stressed_ltv_bps <= solidity_ltv_bps
    # O Health Factor sob estresse deve contrair
    assert stressed_hf < solidity_health_factor
