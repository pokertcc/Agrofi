import json
from typing import Dict, Any, Optional
from web3 import Web3
from eth_account import Account
from web3.logs import DISCARD
from .config import (
    RPC_URL, CHAIN_ID, LOCAL_RPC_URL, SEPOLIA_RPC_URL,
    ACCOUNTS, load_artifact, load_deployed_addresses, save_deployed_addresses
)

class AgroFiWeb3Client:
    def __init__(self, rpc_url: Optional[str] = None):
        target_rpc = rpc_url or RPC_URL
        self.w3 = Web3(Web3.HTTPProvider(target_rpc))
        if not self.w3.is_connected():
            # Tenta fallback entre local Anvil e Sepolia caso um dos dois nao responda
            alt_rpc = SEPOLIA_RPC_URL if "127.0.0.1" in target_rpc or "localhost" in target_rpc else LOCAL_RPC_URL
            try:
                alt_w3 = Web3(Web3.HTTPProvider(alt_rpc))
                if alt_w3.is_connected():
                    self.w3 = alt_w3
                    target_rpc = alt_rpc
            except Exception:
                pass

        if not self.w3.is_connected():
            raise ConnectionError(
                f"Não foi possível conectar ao nó Ethereum/Anvil em {target_rpc}.\n"
                f"• Modo Local: execute 'anvil' em outro terminal.\n"
                f"• Modo Sepolia: verifique a conexão de internet ou defina a variável RPC_URL."
            )

        try:
            self.chain_id = int(self.w3.eth.chain_id)
        except Exception:
            self.chain_id = CHAIN_ID

        self.addresses = load_deployed_addresses(self.chain_id)

        # Contract instances
        self.usdc = None
        self.agro_nft = None
        self.pool = None

        if self.addresses:
            self._init_contracts()

    def _init_contracts(self):
        if "MockUSDC" in self.addresses:
            usdc_artifact = load_artifact("MockUSDC")
            self.usdc = self.w3.eth.contract(
                address=Web3.to_checksum_address(self.addresses["MockUSDC"]),
                abi=usdc_artifact["abi"]
            )
        if "AgroNFT" in self.addresses:
            nft_artifact = load_artifact("AgroNFT")
            self.agro_nft = self.w3.eth.contract(
                address=Web3.to_checksum_address(self.addresses["AgroNFT"]),
                abi=nft_artifact["abi"]
            )
        if "LendingPool" in self.addresses:
            pool_artifact = load_artifact("LendingPool")
            self.pool = self.w3.eth.contract(
                address=Web3.to_checksum_address(self.addresses["LendingPool"]),
                abi=pool_artifact["abi"]
            )

    def deploy_contracts(self, deployer_private_key: str = ACCOUNTS["admin"]["private_key"]) -> Dict[str, str]:
        """
        Deploys MockUSDC, AgroNFT, and LendingPool directly via Web3.py.
        """
        account = Account.from_key(deployer_private_key)
        deployer_addr = account.address

        def _deploy(contract_name: str, *constructor_args):
            artifact = load_artifact(contract_name)
            bytecode = artifact["bytecode"]["object"]
            abi = artifact["abi"]

            factory = self.w3.eth.contract(abi=abi, bytecode=bytecode)
            nonce = self.w3.eth.get_transaction_count(deployer_addr)

            tx = factory.constructor(*constructor_args).build_transaction({
                "from": deployer_addr,
                "nonce": nonce,
                "gas": 6_000_000,
                "gasPrice": self.w3.eth.gas_price,
                "chainId": self.chain_id
            })

            signed_tx = self.w3.eth.account.sign_transaction(tx, deployer_private_key)
            tx_hash = self.w3.eth.send_raw_transaction(signed_tx.raw_transaction)
            receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash)
            return receipt.contractAddress

        # 1. Deploy MockUSDC
        usdc_addr = _deploy("MockUSDC")
        # 2. Deploy AgroNFT
        nft_addr = _deploy("AgroNFT")
        # 3. Deploy LendingPool
        pool_addr = _deploy("LendingPool", usdc_addr, nft_addr)

        self.addresses = {
            "MockUSDC": usdc_addr,
            "AgroNFT": nft_addr,
            "LendingPool": pool_addr
        }
        save_deployed_addresses(self.addresses)
        self._init_contracts()

        # Authorizations: authorize pool and deployer as oracle
        self.send_tx(
            self.agro_nft.functions.setAuthorizedLendingPool(pool_addr, True),
            deployer_private_key
        )
        self.send_tx(
            self.agro_nft.functions.setAuthorizedOracle(deployer_addr, True),
            deployer_private_key
        )
        self.send_tx(
            self.pool.functions.setAuthorizedOracle(deployer_addr, True),
            deployer_private_key
        )

        return self.addresses

    def send_tx(self, contract_func, private_key: str, value: int = 0) -> Any:
        account = Account.from_key(private_key)
        nonce = self.w3.eth.get_transaction_count(account.address)

        tx = contract_func.build_transaction({
            "from": account.address,
            "nonce": nonce,
            "gas": 1_000_000,
            "gasPrice": self.w3.eth.gas_price,
            "chainId": self.chain_id,
            "value": value
        })

        signed = self.w3.eth.account.sign_transaction(tx, private_key)
        tx_hash = self.w3.eth.send_raw_transaction(signed.raw_transaction)
        receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash)
        if receipt.status != 1:
            raise RuntimeError(f"Transaction failed with status {receipt.status}: {tx_hash.hex()}")
        return receipt

    # =========================================================================
    # SPECIFICATION ITEM 5 INTERFACE (Input da Camada Agro)
    # =========================================================================

    def mintCollateral(
        self,
        to: str,
        token_uri: str,
        appraisal_value: int,
        sender_private_key: str = ACCOUNTS["admin"]["private_key"]
    ) -> int:
        """
        Consumes Agro Layer input to tokenize a crop/harvest into an AgroNFT.
        Interface function: mintCollateral(address to, string tokenURI, uint256 appraisalValue)
        """
        to_checksum = Web3.to_checksum_address(to)
        receipt = self.send_tx(
            self.agro_nft.functions.mintCollateral(to_checksum, token_uri, appraisal_value),
            sender_private_key
        )

        # Parse CollateralMinted event
        logs = self.agro_nft.events.CollateralMinted().process_receipt(receipt, errors=DISCARD)
        if logs:
            token_id = logs[0]["args"]["tokenId"]
            return token_id
        return -1

    def updateLTVAndHealthFactor(
        self,
        token_id: int,
        ltv: int,
        health_factor: int,
        sender_private_key: str = ACCOUNTS["admin"]["private_key"]
    ) -> str:
        """
        Consumes Agro Risk Layer input to update dynamic LTV and Health Factor in smart contract.
        Interface function: updateLTVAndHealthFactor(uint256 tokenId, uint256 ltv, uint256 healthFactor)
        """
        receipt = self.send_tx(
            self.pool.functions.updateLTVAndHealthFactor(token_id, ltv, health_factor),
            sender_private_key
        )
        return receipt.transactionHash.hex()

    def borrow(
        self,
        token_id: int,
        amount: int,
        borrower_private_key: str = ACCOUNTS["farmer"]["private_key"]
    ) -> str:
        """
        Executes decentralized loan against tokenized crop collateral.
        Interface function: borrow(uint256 tokenId, uint256 amount)
        """
        receipt = self.send_tx(
            self.pool.functions.borrow(token_id, amount),
            borrower_private_key
        )
        return receipt.transactionHash.hex()

    # =========================================================================
    # SUPPORTING PROTOCOL METHODS
    # =========================================================================

    def deposit_collateral(self, token_id: int, borrower_private_key: str) -> str:
        # First approve pool
        borrower = Account.from_key(borrower_private_key).address
        pool_addr = self.pool.address
        self.send_tx(
            self.agro_nft.functions.approve(pool_addr, token_id),
            borrower_private_key
        )
        # Deposit
        receipt = self.send_tx(
            self.pool.functions.depositCollateral(token_id),
            borrower_private_key
        )
        return receipt.transactionHash.hex()

    def repay(self, token_id: int, amount: int, payer_private_key: str) -> str:
        # Approve USDC
        pool_addr = self.pool.address
        self.send_tx(
            self.usdc.functions.approve(pool_addr, amount),
            payer_private_key
        )
        receipt = self.send_tx(
            self.pool.functions.repay(token_id, amount),
            payer_private_key
        )
        return receipt.transactionHash.hex()

    def withdraw_collateral(self, token_id: int, borrower_private_key: str) -> str:
        receipt = self.send_tx(
            self.pool.functions.withdrawCollateral(token_id),
            borrower_private_key
        )
        return receipt.transactionHash.hex()

    def execute_parametric_liquidation(self, token_id: int, liquidator_private_key: str) -> str:
        # Liquidator approves USDC for outstanding debt
        loan = self.pool.functions.getLoan(token_id).call()
        debt = loan[1]
        pool_addr = self.pool.address
        self.send_tx(
            self.usdc.functions.approve(pool_addr, debt),
            liquidator_private_key
        )
        receipt = self.send_tx(
            self.pool.functions.executeParametricLiquidation(token_id),
            liquidator_private_key
        )
        return receipt.transactionHash.hex()

    def mint_usdc(self, to: str, amount: int, admin_private_key: str = ACCOUNTS["admin"]["private_key"]):
        to_checksum = Web3.to_checksum_address(to)
        return self.send_tx(
            self.usdc.functions.mint(to_checksum, amount),
            admin_private_key
        )

    def deposit_liquidity(self, amount: int, lender_private_key: str):
        pool_addr = self.pool.address
        self.send_tx(
            self.usdc.functions.approve(pool_addr, amount),
            lender_private_key
        )
        return self.send_tx(
            self.pool.functions.depositLiquidity(amount),
            lender_private_key
        )
