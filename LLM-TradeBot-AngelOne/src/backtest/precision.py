"""
Financial Calculation Precision Utils
=============================================

Uses Decimal type for financial calculations to avoid floating-point precision issues

Author: AI Trader Team
Date: 2025-12-31
"""

from decimal import Decimal, ROUND_DOWN, ROUND_HALF_UP, getcontext
from typing import Union
from dataclasses import dataclass
from enum import Enum

# Set global precision
getcontext().prec = 18


class ContractType(Enum):
    """Contract type"""
    LINEAR = "linear"      # USDT-Margined
    INVERSE = "inverse"    # Coin-Margined


@dataclass
class ContractSpec:
    """
    Contract specification
    
    Different exchanges and coins have different contract face values:
    - Binance BTC coin-margined: 1 contract = 100 USD
    - Binance ETH coin-margined: 1 contract = 10 USD
    - OKX BTC coin-margined: 1 contract = 100 USD
    """
    contract_type: ContractType
    contract_size: float = 1.0  # Contract multiplier
    tick_size: float = 0.1      # Minimum price movement
    min_qty: float = 0.001      # Minimum trade quantity
    qty_step: float = 0.001     # Quantity step
    
    # Preset specifications
    @classmethod
    def binance_btc_linear(cls) -> 'ContractSpec':
        """Binance BTCUSDT USDT-margined"""
        return cls(
            contract_type=ContractType.LINEAR,
            contract_size=1.0,
            tick_size=0.1,
            min_qty=0.001,
            qty_step=0.001
        )
    
    @classmethod
    def binance_btc_inverse(cls) -> 'ContractSpec':
        """Binance BTCUSD coin-margined"""
        return cls(
            contract_type=ContractType.INVERSE,
            contract_size=100.0,  # 1 contract = 100 USD
            tick_size=0.1,
            min_qty=1,  # Minimum 1 contract
            qty_step=1
        )
    
    @classmethod
    def binance_eth_inverse(cls) -> 'ContractSpec':
        """Binance ETHUSD coin-margined"""
        return cls(
            contract_type=ContractType.INVERSE,
            contract_size=10.0,  # 1 contract = 10 USD
            tick_size=0.01,
            min_qty=1,
            qty_step=1
        )


class PrecisionCalc:
    """
    High-precision financial calculation class
    
    All financial calculations use Decimal to avoid floating-point error accumulation
    """
    
    PRECISION = 8  # Decimal precision
    
    @staticmethod
    def to_decimal(value: Union[float, str, int, Decimal]) -> Decimal:
        """Convert to Decimal"""
        if isinstance(value, Decimal):
            return value
        return Decimal(str(value))
    
    @staticmethod
    def to_float(value: Decimal) -> float:
        """Convert back to float (for display)"""
        return float(value)
    
    @classmethod
    def round_price(cls, price: Union[float, Decimal], tick_size: float = 0.01) -> Decimal:
        """Round price according to tick size"""
        d_price = cls.to_decimal(price)
        d_tick = cls.to_decimal(tick_size)
        return (d_price / d_tick).quantize(Decimal('1'), rounding=ROUND_DOWN) * d_tick
    
    @classmethod
    def round_qty(cls, qty: Union[float, Decimal], qty_step: float = 0.001) -> Decimal:
        """Round quantity according to qty step"""
        d_qty = cls.to_decimal(qty)
        d_step = cls.to_decimal(qty_step)
        return (d_qty / d_step).quantize(Decimal('1'), rounding=ROUND_DOWN) * d_step
    
    @classmethod
    def calculate_linear_pnl(
        cls,
        entry_price: float,
        exit_price: float,
        quantity: float,
        is_long: bool
    ) -> Decimal:
        """
        Calculate USDT-margined (Linear) contract PnL
        
        Formula: PnL = (exit_price - entry_price) * quantity
        """
        d_entry = cls.to_decimal(entry_price)
        d_exit = cls.to_decimal(exit_price)
        d_qty = cls.to_decimal(quantity)
        
        if is_long:
            return (d_exit - d_entry) * d_qty
        else:
            return (d_entry - d_exit) * d_qty
    
    @classmethod
    def calculate_inverse_pnl(
        cls,
        entry_price: float,
        exit_price: float,
        contracts: int,
        contract_size: float,
        is_long: bool
    ) -> Decimal:
        """
        Calculate coin-margined (Inverse) contract PnL
        
        Formula: PnL = (1/entry - 1/exit) * contracts * contract_size
        
        Note: Coin-margined contract PnL unit is in coin (BTC/ETH), not USDT
        """
        d_entry = cls.to_decimal(entry_price)
        d_exit = cls.to_decimal(exit_price)
        d_contracts = cls.to_decimal(contracts)
        d_size = cls.to_decimal(contract_size)
        
        if is_long:
            # Long: profit when price rises
            pnl = (Decimal('1') / d_entry - Decimal('1') / d_exit) * d_contracts * d_size
        else:
            # Short: profit when price falls
            pnl = (Decimal('1') / d_exit - Decimal('1') / d_entry) * d_contracts * d_size
        
        return pnl
    
    @classmethod
    def calculate_inverse_pnl_usd(
        cls,
        entry_price: float,
        exit_price: float,
        contracts: int,
        contract_size: float,
        is_long: bool,
        settlement_price: float = None
    ) -> Decimal:
        """
        Calculate coin-margined contract PnL (in USD)
        
        Args:
            settlement_price: Settlement price (defaults to exit_price)
        """
        pnl_coin = cls.calculate_inverse_pnl(
            entry_price, exit_price, contracts, contract_size, is_long
        )
        
        # Convert to USD
        settle = cls.to_decimal(settlement_price or exit_price)
        return pnl_coin * settle
    
    @classmethod
    def calculate_liquidation_price(
        cls,
        entry_price: float,
        leverage: int,
        is_long: bool,
        maintenance_margin_rate: float = 0.004,
        contract_type: ContractType = ContractType.LINEAR
    ) -> Decimal:
        """
        Calculate liquidation price
        
        USDT-margined long liquidation: entry * (1 - 1/leverage + mmr)
        USDT-margined short liquidation: entry * (1 + 1/leverage - mmr)
        """
        d_entry = cls.to_decimal(entry_price)
        d_lev = cls.to_decimal(leverage)
        d_mmr = cls.to_decimal(maintenance_margin_rate)
        
        if contract_type == ContractType.LINEAR:
            if is_long:
                # Long liquidation price < entry price
                liq_price = d_entry * (Decimal('1') - Decimal('1') / d_lev + d_mmr)
            else:
                # Short liquidation price > entry price
                liq_price = d_entry * (Decimal('1') + Decimal('1') / d_lev - d_mmr)
        else:
            # Coin-margined calculation is slightly different, simplified here
            if is_long:
                liq_price = d_entry * (Decimal('1') - Decimal('1') / d_lev + d_mmr)
            else:
                liq_price = d_entry * (Decimal('1') + Decimal('1') / d_lev - d_mmr)
        
        return liq_price


# Shortcut functions
def pnl_linear(entry: float, exit: float, qty: float, is_long: bool) -> float:
    """Shortcut to calculate USDT-margined PnL"""
    return float(PrecisionCalc.calculate_linear_pnl(entry, exit, qty, is_long))


def pnl_inverse(entry: float, exit: float, contracts: int, size: float, is_long: bool) -> float:
    """Shortcut to calculate coin-margined PnL (in coin)"""
    return float(PrecisionCalc.calculate_inverse_pnl(entry, exit, contracts, size, is_long))


def pnl_inverse_usd(entry: float, exit: float, contracts: int, size: float, is_long: bool) -> float:
    """Shortcut to calculate coin-margined PnL (in USD)"""
    return float(PrecisionCalc.calculate_inverse_pnl_usd(entry, exit, contracts, size, is_long))


# Test
if __name__ == "__main__":
    print("=" * 50)
    print("🧪 Testing PrecisionCalc")
    print("=" * 50)
    
    # USDT-margined test
    print("\n📊 USDT-margined (Linear) PnL:")
    pnl = pnl_linear(50000, 51000, 0.1, is_long=True)
    print(f"   BTC 50000->51000, 0.1 BTC Long: ${pnl:.2f}")
    
    pnl = pnl_linear(50000, 49000, 0.1, is_long=False)
    print(f"   BTC 50000->49000, 0.1 BTC Short: ${pnl:.2f}")
    
    # Coin-margined test
    print("\n📊 Coin-margined (Inverse) PnL:")
    pnl_btc = pnl_inverse(50000, 51000, 100, 100, is_long=True)
    pnl_usd = pnl_inverse_usd(50000, 51000, 100, 100, is_long=True)
    print(f"   BTC 50000->51000, 100 contracts Long: {pnl_btc:.6f} BTC (${pnl_usd:.2f})")
    
    # Liquidation price
    print("\n📊 Liquidation price calculation:")
    liq = PrecisionCalc.calculate_liquidation_price(50000, 10, True)
    print(f"   BTC 50000 10x Long liquidation price: ${float(liq):.2f}")
    
    liq = PrecisionCalc.calculate_liquidation_price(50000, 10, False)
    print(f"   BTC 50000 10x Short liquidation price: ${float(liq):.2f}")
    
    print("\n✅ PrecisionCalc test complete!")
