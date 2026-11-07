"""Privacy-first Rius tracing. No telemetry is sent without RIUS_API_KEY."""
import os
import logging
from typing import Callable, ParamSpec, TypeVar, cast

P = ParamSpec("P")
R = TypeVar("R")

log = logging.getLogger(__name__)

def initialize():
    """Call once, before instrumented app modules are loaded."""
    from dotenv import load_dotenv
    load_dotenv()
    if not os.getenv("RIUS_API_KEY") or os.getenv("RIUS_DISABLED", "false").lower() in ("1", "true", "yes"):
        log.info("Rius observability disabled (no key or kill switch)")
        return
    try:
        import rius
        rius.init(service_name=os.getenv("RIUS_SERVICE_NAME", "atlas-ai-fde"), capture_content=False)
        log.info("Rius observability enabled")
    except Exception:
        log.exception("Rius initialization failed; application will continue without telemetry")

def trace(name: str) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Decorate sync/async functions; never export arguments or return values."""
    def decorate(fn: Callable[P, R]) -> Callable[P, R]:
        try:
            import rius
            observed = rius.observe(name=name, capture_input=False, capture_output=False)(fn)
            return cast(Callable[P, R], observed)
        except ImportError:
            return fn
    return decorate