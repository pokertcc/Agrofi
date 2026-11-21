// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @dev Interface mínima ERC-20 para staking
 */
interface IERC20Minimal {
    function totalSupply() external view returns (uint256);
    function balanceOf(address account) external view returns (uint256);
    function transfer(address to, uint256 value) external returns (bool);
    function allowance(address owner, address spender) external view returns (uint256);
    function approve(address spender, uint256 value) external returns (bool);
    function transferFrom(address from, address to, uint256 value) external returns (bool);
    function decimals() external view returns (uint8);
}

/**
 * @dev Interface para o AgroToken ($AGRO)
 */
interface IAgroToken is IERC20Minimal {
    function mintRewards(address to, uint256 amount) external returns (bool);
}

/**
 * @title AgroStakingRewards
 * @author AgroFi Protocol
 * @notice Contrato de Staking de Liquidez com Recompensas Contínuas em $AGRO por segundo baseadas em APY.
 * Converte automaticamente as casas decimais do ativo colateral (ex: USDC 6 decimais) para $AGRO (18 decimais).
 */
contract AgroStakingRewards {
    IERC20Minimal public immutable stakingToken;
    IAgroToken public immutable rewardsToken;

    uint8 public immutable stakingDecimals;
    address public owner;

    // APY em pontos base (bps). Ex: 2200 bps = 22.00% a.a.
    uint256 public apyBasisPoints = 2200;
    uint256 public constant BASIS_POINTS_DIVISOR = 10000;
    uint256 public constant SECONDS_PER_YEAR = 365 days;

    uint256 public totalStaked;
    mapping(address => uint256) public stakedBalance;
    mapping(address => uint256) public lastUpdateTime;
    mapping(address => uint256) public storedRewards;

    event Staked(address indexed user, uint256 amount);
    event Withdrawn(address indexed user, uint256 amount);
    event RewardPaid(address indexed user, uint256 reward);
    event ApyUpdated(uint256 newApyBasisPoints);
    event OwnershipTransferred(address indexed previousOwner, address indexed newOwner);

    modifier onlyOwner() {
        require(msg.sender == owner, "AgroStakingRewards: caller is not the owner");
        _;
    }

    modifier updateReward(address account) {
        if (account != address(0)) {
            storedRewards[account] = earned(account);
            lastUpdateTime[account] = block.timestamp;
        }
        _;
    }

    constructor(address _stakingToken, address _rewardsToken, uint256 _initialApyBps) {
        require(_stakingToken != address(0) && _rewardsToken != address(0), "AgroStakingRewards: zero address");
        owner = msg.sender;
        stakingToken = IERC20Minimal(_stakingToken);
        rewardsToken = IAgroToken(_rewardsToken);

        uint8 dec = 18;
        try IERC20Minimal(_stakingToken).decimals() returns (uint8 d) {
            dec = d;
        } catch {}
        stakingDecimals = dec;

        apyBasisPoints = _initialApyBps > 0 ? _initialApyBps : 2200;
        emit OwnershipTransferred(address(0), msg.sender);
    }

    /**
     * @notice Retorna a recompensa acumulada em $AGRO (18 decimais) para a conta especificada.
     */
    function earned(address account) public view returns (uint256) {
        uint256 currentBalance = stakedBalance[account];
        if (currentBalance == 0) {
            return storedRewards[account];
        }

        uint256 timeElapsed = block.timestamp - lastUpdateTime[account];
        uint256 accrued = (currentBalance * apyBasisPoints * timeElapsed) / (BASIS_POINTS_DIVISOR * SECONDS_PER_YEAR);

        // Ajustar casas decimais para 18 decimais do token $AGRO
        if (stakingDecimals < 18) {
            accrued = accrued * (10 ** (18 - stakingDecimals));
        } else if (stakingDecimals > 18) {
            accrued = accrued / (10 ** (stakingDecimals - 18));
        }

        return storedRewards[account] + accrued;
    }

    /**
     * @notice Deposita tokens para staking e início do rendimento.
     */
    function stake(uint256 amount) external updateReward(msg.sender) {
        require(amount > 0, "AgroStakingRewards: cannot stake 0");

        totalStaked += amount;
        stakedBalance[msg.sender] += amount;

        require(stakingToken.transferFrom(msg.sender, address(this), amount), "AgroStakingRewards: transferFrom failed");
        emit Staked(msg.sender, amount);
    }

    /**
     * @notice Retira tokens do staking.
     */
    function withdraw(uint256 amount) public updateReward(msg.sender) {
        require(amount > 0, "AgroStakingRewards: cannot withdraw 0");
        require(stakedBalance[msg.sender] >= amount, "AgroStakingRewards: insufficient staked balance");

        totalStaked -= amount;
        stakedBalance[msg.sender] -= amount;

        require(stakingToken.transfer(msg.sender, amount), "AgroStakingRewards: transfer failed");
        emit Withdrawn(msg.sender, amount);
    }

    /**
     * @notice Reivindica as recompensas acumuladas em $AGRO.
     */
    function claimRewards() public updateReward(msg.sender) returns (uint256) {
        uint256 reward = storedRewards[msg.sender];
        if (reward > 0) {
            storedRewards[msg.sender] = 0;
            require(rewardsToken.mintRewards(msg.sender, reward), "AgroStakingRewards: reward mint failed");
            emit RewardPaid(msg.sender, reward);
        }
        return reward;
    }

    /**
     * @notice Retira todo o saldo e reivindica as recompensas (Exit).
     */
    function exit() external {
        withdraw(stakedBalance[msg.sender]);
        claimRewards();
    }

    /**
     * @notice Atualiza o APY da pool (apenas owner).
     */
    function setApyBasisPoints(uint256 _newApyBps) external onlyOwner {
        require(_newApyBps <= 10000, "AgroStakingRewards: APY too high"); // max 100%
        apyBasisPoints = _newApyBps;
        emit ApyUpdated(_newApyBps);
    }

    /**
     * @notice Transfere o ownership do contrato.
     */
    function transferOwnership(address newOwner) external onlyOwner {
        require(newOwner != address(0), "AgroStakingRewards: zero address");
        emit OwnershipTransferred(owner, newOwner);
        owner = newOwner;
    }
}
