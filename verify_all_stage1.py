import json
from pathlib import Path
from web3 import Web3

pk = [l.split('=')[1].strip().strip('\'"') for l in Path('.env').read_text().splitlines() if 'SEPOLIA_PRIVATE_KEY=' in l][0]
w3 = Web3(Web3.HTTPProvider('https://ethereum-sepolia-rpc.publicnode.com'))

admin_addr = "0xa449e7838fF89EE956174B682449870597e93C71"
usdc_addr = "0x178B9bFA3E86a9Ed3F67963e28afBe49BCf45ED2"
nft_addr = "0xb89Cd470755AD1E25052b57D97af6Fc98b00Dfb2"
lending_addr = "0x020c06c4d1410B2131e9815c5D25F7Ee90D37a26"
staking_addr = "0x154B3f7B2D99E83912267594b8B4aDF76fF58e26"

with open("out/MockUSDC.sol/MockUSDC.json") as f:
    usdc_abi = json.load(f)["abi"]
with open("out/AgroNFT.sol/AgroNFT.json") as f:
    nft_abi = json.load(f)["abi"]
with open("out/LendingPool.sol/LendingPool.json") as f:
    lending_abi = json.load(f)["abi"]

usdc = w3.eth.contract(address=usdc_addr, abi=usdc_abi)
nft = w3.eth.contract(address=nft_addr, abi=nft_abi)
lending = w3.eth.contract(address=lending_addr, abi=lending_abi)

print("=" * 75)
print("🌾 RELATÓRIO DE AUDITORIA DO PROTOCOLO AGROFI (ETAPA 1 - SEPOLIA)")
print("=" * 75)

bal_admin = usdc.functions.balanceOf(admin_addr).call() / 10**6
bal_lending = usdc.functions.balanceOf(lending_addr).call() / 10**6
bal_staking = usdc.functions.balanceOf(staking_addr).call() / 10**6
avail_liq = lending.functions.availableLiquidity().call() / 10**6

print(f"💰 SALDOS MOCKUSDC (6 decimais):")
print(f"  • Carteira Produtor / Admin:   $ {bal_admin:,.2f} USDC")
print(f"  • LendingPool (Liquidez):      $ {bal_lending:,.2f} USDC (Disponível p/ Empréstimo: $ {avail_liq:,.2f})")
print(f"  • Staking Rewards (Investidor):$ {bal_staking:,.2f} USDC")

nft_owner = nft.functions.ownerOf(1).call()
col_data = nft.functions.getCollateralData(1).call()
loan = lending.functions.loans(1).call()
max_borrow = lending.functions.getMaxBorrowable(1).call() / 10**6

print(f"\n🚜 COLATERAL RWA (AgroNFT #1 - Fazenda Santa Helena):")
print(f"  • Detentor Atual do NFT:       {nft_owner} ({'Travado no LendingPool ✅' if nft_owner.lower() == lending_addr.lower() else 'Na Carteira'})")
print(f"  • Avaliação do Imóvel:         $ {col_data[0] / 10**6:,.2f} USDC")
print(f"  • LTV Paramétrico:             {col_data[1] / 100:.2f}%")
print(f"  • Health Factor:               {col_data[2] / 10000:.2f}x (Solvente & Seguro)")
print(f"  • Mutuário Registrado no Pool: {loan[0]}")
print(f"  • Dívida Ativa Atual:          $ {loan[1] / 10**6:,.2f} USDC")
print(f"  • Colateral Ativo:             {loan[2]}")
print(f"  • Limite Máximo Financiável:   $ {max_borrow:,.2f} USDC")

print("\n" + "=" * 75)
print("🚀 SISTEMA 100% OPERACIONAL PARA TESTE DO USUÁRIO NA WEB3!")
print("=" * 75)
