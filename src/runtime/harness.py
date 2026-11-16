"""
Script execution harness for MCP-enabled Python scripts.

This harness:
1. Initializes MCP client manager
2. Executes user script with MCP tools available
3. Handles signals gracefully (SIGINT/SIGTERM)
4. Cleans up all connections on exit
"""

import asyncio
import logging
import runpy
import signal
import sys
from pathlib import Path
from typing import Any, NoReturn

from .env_utils import load_project_env
from .exceptions import McpExecutionError
from .mcp_client import get_mcp_client_manager

# Configure logging to stderr
logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s", stream=sys.stderr)

logger = logging.getLogger("mcp_execution.harness")


def _parse_arguments() -> Path:
    """
    Parse command-line arguments.

    Returns:
        Path to script
    """
    if len(sys.argv) < 2:
        logger.error("Usage: python -m runtime.harness <script_path>")
        sys.exit(1)

    return Path(sys.argv[1]).resolve()


class _AsyncgenErrorFilter(logging.Filter):
    """Filter that suppresses asyncgen cleanup errors from MCP SDK."""

    def filter(self, record: logging.LogRecord) -> bool:
        # Suppress the "error occurred during closing of asynchronous generator" message
        if "asynchronous generator" in record.getMessage().lower():
            return False
        return True


def _suppress_asyncgen_errors():
    """
    Suppress asyncgen cleanup error logs from asyncio.

    The MCP SDK's stdio_client uses async generators that can raise RuntimeErrors
    about cancel scopes when closed in a different task context. These errors are
    harmless cleanup artifacts that we suppress to avoid alarming users.

    This function patches asyncio.run() to install a silent exception handler on
    any event loops it creates, ensuring scripts using asyncio.run() don't see
    these harmless errors.
    """
    # Add filter to asyncio logger to suppress asyncgen cleanup errors
    asyncio_logger = logging.getLogger("asyncio")
    asyncio_logger.addFilter(_AsyncgenErrorFilter())

    # Define silent exception handler
    def silent_exception_handler(loop, context):
        # Suppress asyncgen and cancel scope related errors
        exception = context.get("exception")
        message = context.get("message", "")

        if exception:
            err_str = str(exception).lower()
            if "cancel scope" in err_str or "asyncgen" in err_str:
                return

        if "asyncgen" in message.lower() or "asynchronous generator" in message.lower():
            return

        # For other exceptions, use default handler
        loop.default_exception_handler(context)

    # Store handler for later use
    _suppress_asyncgen_errors._handler = silent_exception_handler

    # Monkey-patch asyncio.run to install our exception handler
    original_run = asyncio.run

    def patched_run(main, *, debug=None, **kwargs):
        # Create loop manually so we can set exception handler
        loop = asyncio.new_event_loop()
        loop.set_exception_handler(silent_exception_handler)
        try:
            asyncio.set_event_loop(loop)
            if debug is not None:
                loop.set_debug(debug)
            return loop.run_until_complete(main)
        finally:
            try:
                # Suppress errors during shutdown
                _cancel_all_tasks(loop)
                loop.run_until_complete(loop.shutdown_asyncgens())
                loop.run_until_complete(loop.shutdown_default_executor())
            except Exception:
                pass
            finally:
                asyncio.set_event_loop(None)
                loop.close()

    asyncio.run = patched_run


def _cancel_all_tasks(loop):
    """Cancel all pending tasks in the loop."""
    to_cancel = asyncio.all_tasks(loop)
    if not to_cancel:
        return

    for task in to_cancel:
        task.cancel()

    loop.run_until_complete(asyncio.gather(*to_cancel, return_exceptions=True))

    for task in to_cancel:
        if task.cancelled():
            continue
        if task.exception() is not None:
            pass  # Suppress task exceptions during cleanup


def _execute_direct(script_path: Path) -> int:
    """
    Execute script in direct mode (current process, no sandbox).

    Args:
        script_path: Path to Python script

    Returns:
        Exit code
    """
    logger.info("=== Direct Mode ===")

    # Add project root and src/ to Python path for imports
    src_path = Path(__file__).parent.parent
    if str(src_path) not in sys.path:
        sys.path.insert(0, str(src_path))
        logger.debug(f"Added to sys.path: {src_path}")

    project_root = src_path.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
        logger.debug(f"Added to sys.path: {project_root}")

    # Suppress asyncgen cleanup errors from MCP SDK
    # This must be done BEFORE any event loop is created
    _suppress_asyncgen_errors()

    # Create persistent event loop
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    # Set exception handler to suppress asyncgen errors
    if hasattr(_suppress_asyncgen_errors, "_handler"):
        loop.set_exception_handler(_suppress_asyncgen_errors._handler)

    # Initialize MCP client manager
    manager = get_mcp_client_manager()
    try:
        loop.run_until_complete(manager.initialize())
        logger.info("MCP client manager initialized")
    except McpExecutionError as e:
        logger.error(f"Failed to initialize MCP client: {e}")
        return 1

    # Set up signal handling
    def signal_handler(signum: int, frame: Any) -> None:
        """Handle shutdown signals."""
        signal_name = signal.Signals(signum).name
        logger.info(f"Received {signal_name}, shutting down...")
        sys.exit(130)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Execute script
    exit_code = 0
    try:
        logger.info(f"Executing script: {script_path}")
        runpy.run_path(str(script_path), run_name="__main__")
        logger.info("Script execution completed")

    except KeyboardInterrupt:
        logger.info("Execution interrupted by user")
        exit_code = 130

    except Exception as e:
        logger.error(f"Script execution failed: {e}", exc_info=True)
        exit_code = 1

    finally:
        # Cleanup
        logger.debug("Cleaning up MCP connections...")
        try:
            loop.run_until_complete(manager.cleanup())
            logger.info("Cleanup complete")
        except BaseException as e:
            # Suppress BaseExceptionGroup from async generators
            if type(e).__name__ == "BaseExceptionGroup":
                logger.debug("Suppressed BaseExceptionGroup during cleanup")
            else:
                logger.error(f"Cleanup failed: {e}", exc_info=True)
                if exit_code == 0:
                    exit_code = 1
        finally:
            # Reset asyncgen hooks before closing loop
            sys.set_asyncgen_hooks(firstiter=None, finalizer=None)
            loop.close()

    return exit_code


def main() -> NoReturn:
    """Entry point for the harness."""
    # 0. Load .env file (if present) for API keys
    if load_project_env():
        logger.info("Loaded .env file")

    # 1. Parse CLI arguments
    script_path = _parse_arguments()

    # 2. Validate script exists
    if not script_path.exists():
        logger.error(f"Script not found: {script_path}")
        sys.exit(1)

    if not script_path.is_file():
        logger.error(f"Not a file: {script_path}")
        sys.exit(1)

    logger.info(f"Script: {script_path}")

    # 3. Execute script
    exit_code = _execute_direct(script_path)

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
