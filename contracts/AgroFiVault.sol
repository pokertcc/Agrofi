// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title AgroFiVault
 * @author Nexus - Arquiteto Web3 & Smart Contracts (AgroFi)
 * @notice Protocolo de Empréstimo Colateralizado em RWA Rural com LTV Dinâmico e Liquidação Paramétrica.
 * @dev Integra dados geoespaciais e modelos de valoração de terras (VTN, SICAR/CAR, SRTM e Sentinel-2 NDVI).
 *      Regula o LTV estritamente no intervalo paramétrico de 35% (3500 bps) a 65% (6500 bps).
 */

/// @dev Interface mínima ERC20 para o ativo de empréstimo (ex: USDC, BRLA, DREX).
interface IERC20 {
    function totalSupply() external view returns (uint256);
    function balanceOf(address account) external view returns (uint256);
    function transfer(address to, uint256 value) external returns (bool);
    function allowance(address owner, address spender) external view returns (uint256);
    function approve(address spender, uint256 value) external returns (bool);
    function transferFrom(address from, address to, uint256 value) external returns (bool);
    event Transfer(address indexed from, address indexed to, uint256 value);
    event Approval(address indexed owner, address indexed spender, uint256 value);
}

/// @dev Interface mínima ERC721 para os títulos RWA de terras agrícolas tokenizadas.
interface IERC721 {
    function ownerOf(uint256 tokenId) external view returns (address owner);
    function safeTransferFrom(address from, address to, uint256 tokenId) external;
    function transferFrom(address from, address to, uint256 tokenId) external;
}

/// @dev Interface para receptores de ERC721
interface IERC721Receiver {
    function onERC721Received(
        address operator,
        address from,
        uint256 tokenId,
        bytes calldata data
    ) external returns (bytes4);
}

/**
 * @dev Biblioteca SafeERC20 para prevenir reverts silenciosos em tokens não conformes.
 */
library SafeERC20 {
    function safeTransfer(IERC20 token, address to, uint256 value) internal {
        require(token.transfer(to, value), "SafeERC20: transfer failed");
    }

    function safeTransferFrom(IERC20 token, address from, address to, uint256 value) internal {
        require(token.transferFrom(from, to, value), "SafeERC20: transferFrom failed");
    }
}

/**
 * @dev Controle de Acesso baseado em Roles (RBAC simplificado).
 */
abstract contract AccessControl {
    bytes32 public constant DEFAULT_ADMIN_ROLE = 0x00;
    bytes32 public constant ORACLE_ROLE = keccak256("ORACLE_ROLE");
    bytes32 public constant LIQUIDATOR_ROLE = keccak256("LIQUIDATOR_ROLE");
    bytes32 public constant EMERGENCY_ROLE = keccak256("EMERGENCY_ROLE");

    mapping(bytes32 => mapping(address => bool)) private _roles;

    event RoleGranted(bytes32 indexed role, address indexed account, address indexed sender);
    event RoleRevoked(bytes32 indexed role, address indexed account, address indexed sender);

    modifier onlyRole(bytes32 role) {
        require(hasRole(role, msg.sender), "AccessControl: unauthorized access");
        _;
    }

    constructor() {
        _roles[DEFAULT_ADMIN_ROLE][msg.sender] = true;
        emit RoleGranted(DEFAULT_ADMIN_ROLE, msg.sender, msg.sender);
    }

    function hasRole(bytes32 role, address account) public view returns (bool) {
        return _roles[role][account];
    }

    function grantRole(bytes32 role, address account) public onlyRole(DEFAULT_ADMIN_ROLE) {
        _roles[role][account] = true;
        emit RoleGranted(role, account, msg.sender);
    }

    function revokeRole(bytes32 role, address account) public onlyRole(DEFAULT_ADMIN_ROLE) {
        _roles[role][account] = false;
        emit RoleRevoked(role, account, msg.sender);
    }
}

/**
 * @dev Proteção contra Reentrância e Pausabilidade.
 */
abstract contract SecurityGuards {
    uint256 private constant _NOT_ENTERED = 1;
    uint256 private constant _ENTERED = 2;
    uint256 private _status = _NOT_ENTERED;

    bool public paused;

    event Paused(address account);
    event Unpaused(address account);

    modifier nonReentrant() {
        require(_status != _ENTERED, "SecurityGuards: reentrant call");
        _status = _ENTERED;
        _;
        _status = _NOT_ENTERED;
    }

    modifier whenNotPaused() {
        require(!paused, "SecurityGuards: protocol is paused");
        _;
    }

    function _pause() internal {
        paused = true;
        emit Paused(msg.sender);
    }

    function _unpause() internal {
        paused = false;
        emit Unpaused(msg.sender);
    }
}

contract AgroFiVault is AccessControl, SecurityGuards, IERC721Receiver {
    using SafeERC20 for IERC20;

    // --- CONSTANTES PARAMÉTRICAS DO PROTOCOLO ---
    uint256 public constant BPS_DENOMINATOR = 10_000;       // 100% = 10,000 bps
    uint256 public constant MIN_LTV_BPS = 3_500;            // 35.00% (Limite mínimo estrito)
    uint256 public constant MAX_LTV_BPS = 6_500;            // 65.00% (Limite máximo estrito)
    uint256 public constant HF_PRECISION = 1e18;            // Precisão do Health Factor (1.0 = 1e18)
    uint256 public constant LIQUIDATION_THRESHOLD_HF = 1e18; // HF < 1.0 ativa liquidação paramétrica
    uint256 public constant LIQUIDATION_DISCOUNT_BPS = 500;  // 5% de bônus/incentivo para o liquidante
    uint256 public constant ORACLE_VALIDITY_WINDOW = 3 days; // Máxima tolerância de tempo (heartbeat)

    // --- ATIVOS DO PROTOCOLO ---
    IERC721 public immutable landNftContract; // Contrato do NFT RWA da terra rural
    IERC20 public immutable debtStablecoin;  // Ativo de crédito (ex: BRLA / USDC)

    // --- ESTRUTURAS DE DADOS DO ORÁCULO E COLATERAL ---

    /// @notice Payload estrito espelhado no Web3CollateralPayload da API AgroFi
    struct ValuationOracleData {
        string landId;          // Ex: "TALHAO-MT-001"
        string carCode;         // Ex: "MT-5107925-8A4F1D9C3E2B4A1F8C2D3E4F5A6B7C8D"
        uint256 predictedValue; // Valoração patrimonial pelo modelo (em unidades monetárias 18 decimais)
        uint256 ltvRatioBps;    // LTV dinâmico estritamente entre 3500 e 6500 (35% a 65%)
        uint256 healthFactor;   // Health factor reportado pelo motor estocástico (1e18)
        uint256 updatedAt;      // Timestamp da última atualização do oráculo
    }

    /// @notice Posição de colateral e dívida de cada imóvel
    struct VaultPosition {
        address borrower;       // Titular que depositou o colateral e tomou empréstimo
        uint256 tokenId;        // Token ID do NFT de terra RWA
        uint256 borrowedDebt;   // Dívida ativa tomada pelo mutuário
        uint256 lastAccrualTime;// Timestamp para eventual taxa de juros
        bool isCollateralized;  // Se o colateral está travado no vault
    }

    // Mapeamento: tokenId -> Dados do Oráculo
    mapping(uint256 => ValuationOracleData) public oracleDataByToken;

    // Mapeamento: tokenId -> Posição de Crédito
    mapping(uint256 => VaultPosition) public positions;

    // Mapeamento: hash(landId) -> tokenId registrado
    mapping(bytes32 => uint256) public landIdToTokenId;

    // --- EVENTOS DO SISTEMA ---
    event LandValuationUpdated(
        uint256 indexed tokenId,
        string landId,
        string carCode,
        uint256 predictedValue,
        uint256 ltvRatioBps,
        uint256 healthFactor,
        uint256 timestamp
    );

    event CollateralDeposited(
        address indexed borrower,
        uint256 indexed tokenId,
        string landId,
        uint256 timestamp
    );

    event CollateralWithdrawn(
        address indexed borrower,
        uint256 indexed tokenId,
        uint256 timestamp
    );

    event DebtBorrowed(
        address indexed borrower,
        uint256 indexed tokenId,
        uint256 amountBorrowed,
        uint256 totalDebt,
        uint256 currentHealthFactor
    );

    event DebtRepaid(
        address indexed borrower,
        uint256 indexed tokenId,
        uint256 amountRepaid,
        uint256 remainingDebt
    );

    event ParametricLiquidationExecuted(
        uint256 indexed tokenId,
        address indexed liquidator,
        address indexed borrower,
        uint256 debtLiquidated,
        uint256 collateralValueSettled,
        uint256 triggerHealthFactor
    );

    // --- ERROS CUSTOMIZADOS PARA EFICIÊNCIA DE GAS ---
    error LtvOutOfRange(uint256 providedBps, uint256 minBps, uint256 maxBps);
    error StaleOracleData(uint256 oracleTime, uint256 currentTime);
    error CollateralAlreadyDeposited(uint256 tokenId);
    error CollateralNotDeposited(uint256 tokenId);
    error NotBorrowerOrOwner();
    error DebtExceedsDynamicLtv(uint256 requestedDebt, uint256 maxBorrowAllowed);
    error PositionNotLiquidatable(uint256 healthFactor, uint256 threshold);
    error OutstandingDebtRemains(uint256 remainingDebt);
    error InvalidZeroAddress();
    error InvalidZeroAmount();

    /**
     * @notice Construtor de inicialização do Vault AgroFi
     * @param _landNft Endereço do contrato ERC721 das terras agrícolas RWA
     * @param _stablecoin Endereço do ERC20 utilizado para liquidez e concessão de crédito
     * @param _initialOracle Endereço do nó oráculo/relayer autorizado
     */
    constructor(
        address _landNft,
        address _stablecoin,
        address _initialOracle
    ) {
        if (_landNft == address(0) || _stablecoin == address(0) || _initialOracle == address(0)) {
            revert InvalidZeroAddress();
        }

        landNftContract = IERC721(_landNft);
        debtStablecoin = IERC20(_stablecoin);

        grantRole(ORACLE_ROLE, _initialOracle);
        grantRole(LIQUIDATOR_ROLE, msg.sender);
        grantRole(EMERGENCY_ROLE, msg.sender);
    }

    // --- ATUALIZAÇÃO DO ORÁCULO GEOESPACIAL & MOTOR DE RISCO ---

    /**
     * @notice Atualiza o valuation patrimonial e LTV dinâmico calculados pelo pipeline de ML e sensoriamento remoto
     * @dev Apenas contas com ORACLE_ROLE podem submeter valuations.
     * @param tokenId ID do token ERC721 correspondente ao imóvel rural
     * @param landId Identificador único do talhão (ex: "TALHAO-MT-001")
     * @param carCode Código oficial do Cadastro Ambiental Rural
     * @param predictedValue Valoração patrimonial estimada pelo modelo (em wei / 18 decimals)
     * @param ltvRatioBps LTV dinâmico em Basis Points (deve estar estritamente entre 3500 e 6500)
     * @param healthFactor Fator de saúde calculado pelo oráculo (1e18 = 1.0)
     */
    function updateLandValuation(
        uint256 tokenId,
        string calldata landId,
        string calldata carCode,
        uint256 predictedValue,
        uint256 ltvRatioBps,
        uint256 healthFactor
    ) external onlyRole(ORACLE_ROLE) whenNotPaused {
        if (ltvRatioBps < MIN_LTV_BPS || ltvRatioBps > MAX_LTV_BPS) {
            revert LtvOutOfRange(ltvRatioBps, MIN_LTV_BPS, MAX_LTV_BPS);
        }

        oracleDataByToken[tokenId] = ValuationOracleData({
            landId: landId,
            carCode: carCode,
            predictedValue: predictedValue,
            ltvRatioBps: ltvRatioBps,
            healthFactor: healthFactor,
            updatedAt: block.timestamp
        });

        bytes32 landKey = keccak256(abi.encodePacked(landId));
        landIdToTokenId[landKey] = tokenId;

        emit LandValuationUpdated(
            tokenId,
            landId,
            carCode,
            predictedValue,
            ltvRatioBps,
            healthFactor,
            block.timestamp
        );
    }

    // --- OPERAÇÕES DO MUTUÁRIO (BORROWER) ---

    /**
     * @notice Deposita o NFT representativo da terra rural no Vault como colateral.
     * @dev O usuário precisa conceder approve ou setApprovalForAll para o contrato AgroFiVault.
     * @param tokenId Identificador do NFT RWA da terra
     */
    function depositCollateral(uint256 tokenId) external nonReentrant whenNotPaused {
        VaultPosition storage pos = positions[tokenId];
        if (pos.isCollateralized) {
            revert CollateralAlreadyDeposited(tokenId);
        }

        // Transfere o NFT para custódia do Vault
        landNftContract.safeTransferFrom(msg.sender, address(this), tokenId);

        pos.borrower = msg.sender;
        pos.tokenId = tokenId;
        pos.isCollateralized = true;
        pos.lastAccrualTime = block.timestamp;

        ValuationOracleData storage oracle = oracleDataByToken[tokenId];

        emit CollateralDeposited(msg.sender, tokenId, oracle.landId, block.timestamp);
    }

    /**
     * @notice Toma empréstimo em stablecoin garantido pelo colateral rural depositado.
     * @dev Valida se a dívida acumulada não excede o LTV Dinâmico parametrizado pelo oráculo.
     * @param tokenId ID do colateral depositado
     * @param amountToBorrow Montante de liquidez solicitado (em unidades do token estável)
     */
    function borrow(uint256 tokenId, uint256 amountToBorrow) external nonReentrant whenNotPaused {
        if (amountToBorrow == 0) revert InvalidZeroAmount();

        VaultPosition storage pos = positions[tokenId];
        if (!pos.isCollateralized) revert CollateralNotDeposited(tokenId);
        if (pos.borrower != msg.sender) revert NotBorrowerOrOwner();

        ValuationOracleData storage oracle = oracleDataByToken[tokenId];
        _validateOracleFreshness(oracle.updatedAt);

        uint256 newTotalDebt = pos.borrowedDebt + amountToBorrow;
        uint256 maxBorrowAllowed = (oracle.predictedValue * oracle.ltvRatioBps) / BPS_DENOMINATOR;

        if (newTotalDebt > maxBorrowAllowed) {
            revert DebtExceedsDynamicLtv(newTotalDebt, maxBorrowAllowed);
        }

        pos.borrowedDebt = newTotalDebt;
        pos.lastAccrualTime = block.timestamp;

        // Transfere os fundos para o produtor rural
        debtStablecoin.safeTransfer(msg.sender, amountToBorrow);

        uint256 currentHf = computeHealthFactor(tokenId);

        emit DebtBorrowed(msg.sender, tokenId, amountToBorrow, newTotalDebt, currentHf);
    }

    /**
     * @notice Amortiza ou quita integralmente a dívida do empréstimo.
     * @param tokenId ID do colateral rural
     * @param amountToRepay Montante que o mutuário deseja pagar
     */
    function repay(uint256 tokenId, uint256 amountToRepay) external nonReentrant whenNotPaused {
        if (amountToRepay == 0) revert InvalidZeroAmount();

        VaultPosition storage pos = positions[tokenId];
        if (!pos.isCollateralized) revert CollateralNotDeposited(tokenId);

        uint256 currentDebt = pos.borrowedDebt;
        uint256 actualRepayment = amountToRepay > currentDebt ? currentDebt : amountToRepay;

        pos.borrowedDebt = currentDebt - actualRepayment;
        pos.lastAccrualTime = block.timestamp;

        // Puxa a stablecoin do pagador para o Vault
        debtStablecoin.safeTransferFrom(msg.sender, address(this), actualRepayment);

        emit DebtRepaid(msg.sender, tokenId, actualRepayment, pos.borrowedDebt);
    }

    /**
     * @notice Resgata o NFT de terra colateralizada de volta à carteira do produtor.
     * @dev Requer quitação integral da dívida antes da liberação da garantia.
     * @param tokenId ID do NFT a ser retirado
     */
    function withdrawCollateral(uint256 tokenId) external nonReentrant whenNotPaused {
        VaultPosition storage pos = positions[tokenId];
        if (!pos.isCollateralized) revert CollateralNotDeposited(tokenId);
        if (pos.borrower != msg.sender) revert NotBorrowerOrOwner();
        if (pos.borrowedDebt > 0) revert OutstandingDebtRemains(pos.borrowedDebt);

        pos.isCollateralized = false;
        pos.borrower = address(0);

        // Devolve o NFT ao produtor
        landNftContract.safeTransferFrom(address(this), msg.sender, tokenId);

        emit CollateralWithdrawn(msg.sender, tokenId, block.timestamp);
    }

    // --- MOTOR DE LIQUIDAÇÃO PARAMÉTRICA ---

    /**
     * @notice Executa a liquidação paramétrica de um colateral rural quando o Health Factor cai abaixo de 1.0 (HF < 1e18)
     * @dev O gatilho pode ser ativado por choque hídrico severo (anomalia de NDVI), risco ambiental no CAR,
     *      ou queda abrupta no valor patrimonial predito pelo oráculo.
     * @param tokenId ID do NFT cujo colateral sofreu quebra de solvência paramétrica
     */
    function executeParametricLiquidation(uint256 tokenId) external nonReentrant whenNotPaused {
        VaultPosition storage pos = positions[tokenId];
        if (!pos.isCollateralized) revert CollateralNotDeposited(tokenId);
        if (pos.borrowedDebt == 0) revert InvalidZeroAmount();

        ValuationOracleData storage oracle = oracleDataByToken[tokenId];
        _validateOracleFreshness(oracle.updatedAt);

        uint256 currentHf = computeHealthFactor(tokenId);
        if (currentHf >= LIQUIDATION_THRESHOLD_HF) {
            revert PositionNotLiquidatable(currentHf, LIQUIDATION_THRESHOLD_HF);
        }

        address originalBorrower = pos.borrower;
        uint256 totalDebtToCover = pos.borrowedDebt;

        // Zera a dívida da posição
        pos.borrowedDebt = 0;
        pos.isCollateralized = false;
        pos.borrower = address(0);

        // Liquidante cobre o montante devido em stablecoins
        debtStablecoin.safeTransferFrom(msg.sender, address(this), totalDebtToCover);

        // O NFT da terra RWA é adjudicado e transferido para o liquidante / fundo de resgate
        landNftContract.safeTransferFrom(address(this), msg.sender, tokenId);

        emit ParametricLiquidationExecuted(
            tokenId,
            msg.sender,
            originalBorrower,
            totalDebtToCover,
            oracle.predictedValue,
            currentHf
        );
    }

    // --- FUNÇÕES DE CÁLCULO E CONSULTA ON-CHAIN (VIEWS) ---

    /**
     * @notice Calcula o Health Factor em tempo de execução:
     *         HF = (predictedValue * ltvRatioBps * 1e18) / (borrowedDebt * BPS_DENOMINATOR)
     * @param tokenId ID do colateral
     * @return hf Fator de saúde escalado em 1e18 (1e18 representa 1.000)
     */
    function computeHealthFactor(uint256 tokenId) public view returns (uint256 hf) {
        VaultPosition memory pos = positions[tokenId];
        if (pos.borrowedDebt == 0) {
            return type(uint256).max; // Dívida zero = Solvência infinita
        }

        ValuationOracleData memory oracle = oracleDataByToken[tokenId];
        if (oracle.predictedValue == 0 || oracle.ltvRatioBps == 0) {
            return 0; // Sem valuation ativo = insolvência imediata
        }

        // Capacidade máxima de crédito tolerada pelo colateral
        uint256 maxCreditCapacity = (oracle.predictedValue * oracle.ltvRatioBps) / BPS_DENOMINATOR;

        // HF = (Capacidade de Crédito / Dívida Atual) * 1e18
        hf = (maxCreditCapacity * HF_PRECISION) / pos.borrowedDebt;
        return hf;
    }

    /**
     * @notice Retorna a capacidade disponível de empréstimo (Borrow Power) para uma terra
     * @param tokenId ID do colateral
     */
    function getAvailableBorrowPower(uint256 tokenId) external view returns (uint256 available) {
        VaultPosition memory pos = positions[tokenId];
        if (!pos.isCollateralized) return 0;

        ValuationOracleData memory oracle = oracleDataByToken[tokenId];
        uint256 maxBorrowAllowed = (oracle.predictedValue * oracle.ltvRatioBps) / BPS_DENOMINATOR;

        if (maxBorrowAllowed <= pos.borrowedDebt) {
            return 0;
        }

        return maxBorrowAllowed - pos.borrowedDebt;
    }

    /**
     * @notice Retorna visão agregada da posição e do oráculo para interfaces Web3
     */
    function getFullPositionDetails(uint256 tokenId) external view returns (
        address borrower,
        uint256 borrowedDebt,
        bool isCollateralized,
        string memory landId,
        string memory carCode,
        uint256 predictedValue,
        uint256 ltvRatioBps,
        uint256 onChainHealthFactor,
        uint256 oracleUpdatedAt,
        bool isLiquidatable
    ) {
        VaultPosition memory pos = positions[tokenId];
        ValuationOracleData memory oracle = oracleDataByToken[tokenId];
        uint256 hf = computeHealthFactor(tokenId);
        bool canLiquidate = (pos.isCollateralized && pos.borrowedDebt > 0 && hf < LIQUIDATION_THRESHOLD_HF);

        return (
            pos.borrower,
            pos.borrowedDebt,
            pos.isCollateralized,
            oracle.landId,
            oracle.carCode,
            oracle.predictedValue,
            oracle.ltvRatioBps,
            hf,
            oracle.updatedAt,
            canLiquidate
        );
    }

    // --- FUNÇÕES INTERNAS E DE GOVERNANÇA ---

    function _validateOracleFreshness(uint256 updatedAt) internal view {
        if (updatedAt == 0 || block.timestamp > updatedAt + ORACLE_VALIDITY_WINDOW) {
            revert StaleOracleData(updatedAt, block.timestamp);
        }
    }

    function pause() external onlyRole(EMERGENCY_ROLE) {
        _pause();
    }

    function unpause() external onlyRole(DEFAULT_ADMIN_ROLE) {
        _unpause();
    }

    /// @inheritdoc IERC721Receiver
    function onERC721Received(
        address,
        address,
        uint256,
        bytes calldata
    ) external view override returns (bytes4) {
        require(msg.sender == address(landNftContract), "AgroFiVault: Invalid NFT origin");
        return this.onERC721Received.selector;
    }
}
