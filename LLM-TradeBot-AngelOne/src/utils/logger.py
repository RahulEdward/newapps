"""
Logging Utility Module - Enhanced version with colored output and LLM-specific logging
"""
import sys
import json
from pathlib import Path
from loguru import logger
from src.config import config


class ColoredLogger:
    """Colored logger wrapper"""
    
    def __init__(self, logger_instance):
        self._logger = logger_instance
    
    def __getattr__(self, name):
        """Forward other methods to original logger"""
        return getattr(self._logger, name)
    
    def llm_input(self, message: str, context: str = None):
        """Log LLM input (cyan background)"""
        self._logger.opt(colors=True).info(
            f"<bold><cyan>{'=' * 60}</cyan></bold>\n"
            f"<bold><cyan>LLM Input</cyan></bold>\n"
            f"<bold><cyan>{'=' * 60}</cyan></bold>"
        )
        if context:
            # Truncate overly long context
            if len(context) > 5000:
                display_context = context[:2000] + "\n... (middle section omitted) ...\n" + context[-2000:]
            else:
                display_context = context
            self._logger.opt(colors=True).info(f"<cyan>{display_context}</cyan>")
        self._logger.opt(colors=True).info(f"<bold><cyan>{'=' * 60}</cyan></bold>\n")
    
    def llm_output(self, message: str, decision: dict = None):
        """Log LLM output (light yellow background)"""
        from src.utils.json_utils import safe_json_dumps
        self._logger.opt(colors=True).info(
            f"<bold><light-yellow>{'=' * 60}</light-yellow></bold>\n"
            f"<bold><light-yellow>LLM Output</light-yellow></bold>\n"
            f"<bold><light-yellow>{'=' * 60}</light-yellow></bold>"
        )
        if decision:
            formatted_json = safe_json_dumps(decision, indent=2, ensure_ascii=False)
            self._logger.opt(colors=True).info(f"<light-yellow>{formatted_json}</light-yellow>")
        self._logger.opt(colors=True).info(f"<bold><light-yellow>{'=' * 60}</light-yellow></bold>\n")
    
    def llm_decision(self, action: str, confidence: int, reasoning: str = None):
        """Log LLM decision (light color highlight)"""
        # Choose color based on action type (using light tones)
        action_colors = {
            'open_long': 'light-green',
            'add_position': 'light-green',
            'open_short': 'light-red',
            'close_position': 'light-yellow',
            'reduce_position': 'light-yellow',
            'hold': 'light-blue'
        }
        color = action_colors.get(action, 'white')
        
        self._logger.opt(colors=True).info(
            f"<bold><{color}>{'=' * 60}</{color}></bold>\n"
            f"<bold><{color}>Trading Decision</{color}></bold>\n"
            f"<bold><{color}>{'=' * 60}</{color}></bold>\n"
            f"<bold><{color}>Action: {action.upper()}</{color}></bold>\n"
            f"<bold><{color}>Confidence: {confidence}%</{color}></bold>"
        )
        if reasoning:
            # Truncate overly long reasoning
            if len(reasoning) > 500:
                display_reasoning = reasoning[:500] + "..."
            else:
                display_reasoning = reasoning
            self._logger.opt(colors=True).info(
                f"<{color}>Reason: {display_reasoning}</{color}>"
            )
        self._logger.opt(colors=True).info(
            f"<bold><{color}>{'=' * 60}</{color}></bold>\n"
        )
    
    def risk_alert(self, message: str):
        """Log risk alert (light red)"""
        self._logger.opt(colors=True).warning(
            f"<bold><light-red>Risk Alert: {message}</light-red></bold>"
        )
    
    # === AIF Semantic Logging Methods (Adversarial Intelligence Framework) ===
    
    def oracle(self, message: str):
        """[THE ORACLE] Log data sampling (blue)"""
        self._logger.opt(colors=True).info(f"<blue>[Oracle] {message}</blue>")
        
    def strategist(self, message: str):
        """[THE STRATEGIST] Log strategy hypothesis (purple)"""
        self._logger.opt(colors=True).info(f"<magenta>[Strategist] {message}</magenta>")
        
    def critic(self, message: str, challenge: bool = False):
        """[THE CRITIC] Log adversarial audit (orange)"""
        icon = "⚖️" if not challenge else "⚔️"
        color = "yellow" if not challenge else "red"
        self._logger.opt(colors=True).info(f"<{color}>{icon} [Critic] {message}</{color}>")
        
    def guardian(self, message: str, blocked: bool = False):
        """[THE GUARDIAN] Log risk control audit (green/red)"""
        icon = "👮" if not blocked else "🚫"
        color = "green" if not blocked else "light-red"
        self._logger.opt(colors=True).info(f"<{color}>{icon} [Guardian] {message}</{color}>")
        
    def executor(self, message: str, success: bool = True):
        """[THE EXECUTOR] Log execution command (highlight)"""
        icon = "🚀" if success else "❌"
        color = "light-green" if success else "light-red"
        self._logger.opt(colors=True).info(f"<bold><{color}>{icon} [Executor] {message}</{color}></bold>")

    # Compatibility aliases
    market_data = oracle
    trade_execution = executor


def setup_logger():
    """Configure logging system"""
    # Remove default handler
    logger.remove()
    
    # Console output - enable colors
    logger.add(
        sys.stdout,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>",
        level=config.logging.get('level', 'INFO'),
        colorize=True
    )
    
    # File output - no color codes
    # Use date subdirectory: logs/YYYY-MM-DD/trading.log
    log_file = config.logging.get('file', 'logs/trading.log')
    log_path = Path(log_file)
    # 1. Dashboard Log (Clean) -> trading.log
    # Dynamically generate path format with date
    dynamic_log_file = str(log_path.parent / "{time:YYYY-MM-DD}" / log_path.name)
    
    logger.add(
        dynamic_log_file,
        format="{time:YYYY-MM-DD HH:mm:ss} {message}", 
        filter=lambda record: record["extra"].get("dashboard") is True,
        level="INFO",
        rotation="00:00",
        retention="30 days",
        compression="zip"
    )

    # 2. System Debug Log (Verbose) -> debug.log
    debug_log_file = str(log_path.parent / "{time:YYYY-MM-DD}" / "debug.log")
    logger.add(
        debug_log_file,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function} - {message}",
        level="DEBUG",
        rotation="00:00",
        retention="7 days",
        compression="zip"
    )
    
    return ColoredLogger(logger)


# Global logger instance
log = setup_logger()
