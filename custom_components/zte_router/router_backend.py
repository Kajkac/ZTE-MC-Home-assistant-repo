import logging
from typing import Optional

from . import mc
from .const import ROUTER_TYPE_G5_ULTRA
from .g5_ultra_client import G5UltraRouterRunner

LOGGER = logging.getLogger(__name__)


def run_router_commands(
    router_type: str,
    ip: str,
    password: str,
    username: Optional[str],
    commands: str,
    phone_number: Optional[str] = None,
    message: Optional[str] = None,
) -> str:
    """Execute router commands using the appropriate backend."""
    if router_type == ROUTER_TYPE_G5_ULTRA:
        runner = G5UltraRouterRunner(ip, password)
        return runner.run_commands(commands, phone=phone_number, message=message)
    return _run_mc_commands(ip, password, username, commands, phone_number, message)


def _run_mc_commands(
    ip: str,
    password: str,
    username: Optional[str],
    commands: str,
    phone_number: Optional[str],
    message: Optional[str],
) -> str:
    """Run MC-series commands in-process via zteRouter (mc.py)."""
    LOGGER.debug("Executing MC router command(s): %s", commands)
    return mc.run_commands(
        str(ip), str(password), username, commands, phone_number=phone_number, message=message
    )
