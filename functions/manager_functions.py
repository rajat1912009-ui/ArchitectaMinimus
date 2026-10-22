"""Reusable functions for the route manager."""

import os 
import time
import json
from pathlib import Path
import queue
import subprocess
import sys 
import threading

# =========================
# Paths and defaults
# =========================

PROJECT_ROOT = Path(__file__).resolve().parent.parent

STRATEGIES_DIR = PROJECT_ROOT / "strategies"
DEFAULT_STRATEGY = "strategy1"

ABBREVIATIONS_PATH = PROJECT_ROOT / "config" / "abbreviations.json"
COORDINATES_PATH = PROJECT_ROOT / "config" / "coordinates.json"


# =========================
# 1. Configuration and loading
# =========================

def load_route(strategy_name=DEFAULT_STRATEGY):
    """Load a selected JSON route from the strategies directory."""

    strategy_path = Path(strategy_name)

    # Allow an explicit JSON filename, or a strategy name without extension.
    if strategy_path.suffix.lower() != ".json":
        strategy_path = strategy_path.with_suffix(".json")

    # Prevent absolute paths and directory traversal outside strategies/.
    if strategy_path.is_absolute() or ".." in strategy_path.parts:
        raise ValueError("Strategy must be a filename inside strategies/.")

    route_path = STRATEGIES_DIR / strategy_path

    try:
        with route_path.open("r", encoding="utf-8") as file:
            return json.load(file)
    except FileNotFoundError:
        raise FileNotFoundError(
            f"Strategy not found: {route_path}"
        ) from None
    except json.JSONDecodeError as error:
        raise ValueError(
            f"Invalid JSON in {route_path.name}, "
            f"line {error.lineno}, column {error.colno}: {error.msg}"
        ) from error


def load_abbreviations():
    """Load command abbreviation definitions from config/abbreviations.json."""

    try:
        with ABBREVIATIONS_PATH.open("r", encoding="utf-8") as file:
            abbreviations = json.load(file)
    except FileNotFoundError:
        raise FileNotFoundError(
            f"Abbreviation file not found: {ABBREVIATIONS_PATH}"
        ) from None
    except json.JSONDecodeError as error:
        raise ValueError(
            f"Invalid abbreviation JSON at line {error.lineno}, "
            f"column {error.colno}: {error.msg}"
        ) from error

    if not isinstance(abbreviations, dict):
        raise ValueError("Abbreviation file must contain a JSON object.")

    return abbreviations


def load_coordinates():
    """Load named coordinates from config/coordinates.json."""

    try:
        with COORDINATES_PATH.open("r", encoding="utf-8") as file:
            coordinates = json.load(file)
    except FileNotFoundError:
        raise FileNotFoundError(
            f"Coordinates file not found: {COORDINATES_PATH}"
        ) from None
    except json.JSONDecodeError as error:
        raise ValueError(
            f"Invalid coordinates JSON at line {error.lineno}, "
            f"column {error.colno}: {error.msg}"
        ) from error

    if not isinstance(coordinates, dict):
        raise ValueError("Coordinates file must contain a JSON object.")

    return coordinates


def validate_route(route):
    """Catch basic route problems without attempting to validate its logic."""

    if not isinstance(route, (dict, list)):
        raise ValueError("Route must be a JSON object or array.")

    if not route:
        raise ValueError("Route is empty.")

    # Detailed checks depend on the instruction format we define later.
    return True


# =========================
# 2. Instruction resolution
# =========================


def resolve_instruction(instruction, abbreviations):
    """Identify whether an instruction name refers to control flow or an action."""

    if not isinstance(instruction, dict) or len(instruction) != 1:
        raise ValueError(
            "Each instruction must be an object with exactly one command."
        )

    name, raw_arguments = next(iter(instruction.items()))

    if name in abbreviations["instructions"]:
        kind = "instruction"
        definition = abbreviations["instructions"][name]
    elif name in abbreviations["actions"]:
        kind = "action"
        definition = abbreviations["actions"][name]
    else:
        raise ValueError(f"Unknown instruction or action: {name}")

    if raw_arguments is None:
        raw_arguments = []

    return {
        "kind": kind,
        "name": name,
        "definition": definition,
        "arguments": raw_arguments,
    }


def resolve_arguments(arguments, coordinates):
    """Resolve named coordinate references while preserving ordinary values."""

    if isinstance(arguments, str):
        if arguments in coordinates:
            return coordinates[arguments]
        return arguments

    if isinstance(arguments, list):
        return [
            resolve_arguments(argument, coordinates)
            for argument in arguments
        ]

    if isinstance(arguments, dict):
        return {
            key: resolve_arguments(value, coordinates)
            for key, value in arguments.items()
        }

    # Numbers, booleans, and null are passed through unchanged.
    return arguments


def resolve_action(name, abbreviations):
    """Look up an action definition without executing it."""

    actions = abbreviations.get("actions", {})

    if name not in actions:
        raise ValueError(f"Unknown action: {name}")

    return actions[name]


# =========================
# 3. Runtime and process management
# =========================



def _build_command(script_path, arguments=None):
    """Build the command used to launch a Python or shell script."""
    import os
    import sys
    from pathlib import Path

    script_path = Path(script_path)
    arguments = [] if arguments is None else arguments
    arguments = [str(argument) for argument in arguments]

    if script_path.suffix == ".py":
        return [sys.executable, str(script_path), *arguments]

    if script_path.suffix == ".sh":
        return ["bash", str(script_path), *arguments]

    if not os.access(script_path, os.X_OK):
        raise PermissionError(f"Script is not executable: {script_path}")

    return [str(script_path), *arguments]


def _read_service_output(process, events):
    """Read a service's output in the background and publish events."""
    try:
        for line in process.stdout:
            value = line.strip()

            if value:
                events.put(("OUTPUT", value))

    except Exception as error:
        events.put(("ERROR", str(error)))

    finally:
        events.put(("EOF", None))


def start_service(name, abbreviations, runtime):
    """Start a declared persistent service; reject undeclared services."""
    definition = abbreviations.get("services", {}).get(name)

    if definition is None:
        raise ValueError(f"Not declared as a persistent service: {name}")

    existing = runtime["services"].get(name)
    if existing and existing["process"].poll() is None:
        return existing["process"]

    script_path = _resolve_script(definition["target"])
    command = _build_command(script_path, definition.get("arguments", []))
    events = queue.Queue()

    process = subprocess.Popen(
        command,
        env={**os.environ, "PYTHONPATH": str(PROJECT_ROOT)}, 
        cwd=script_path.parent.parent,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )

    runtime["services"][name] = {
        "process": process,
        "events": events,
        "last_result": None,
    }

    threading.Thread(
        target=_read_service_output,
        args=(process, events),
        daemon=True,
    ).start()

    return process


def send_service_command(name, command, abbreviations, runtime):
    """Send a declared command to a running service."""
    service_definition = abbreviations.get("services", {}).get(name)
    if service_definition is None:
        raise ValueError(f"Unknown service: {name}")

    commands = service_definition.get("commands", {})
    if command not in commands:
        raise ValueError(f"Undeclared command {command!r} for service {name}")

    entry = runtime["services"].get(name)
    if entry is None or entry["process"].poll() is not None:
        raise RuntimeError(f"Service is not running: {name}")

    process = entry["process"]
    process.stdin.write(f"{commands[command]}\n")
    process.stdin.flush()


def read_service_event(name, runtime, timeout=None):
    """Read the next available event from a service without blocking forever."""
    entry = runtime["services"].get(name)
    if entry is None:
        raise ValueError(f"Service has not been started: {name}")

    try:
        event_type, value = entry["events"].get(timeout=timeout)
    except queue.Empty:
        return None

    if event_type == "OUTPUT":
        # Keep protocol output separate from diagnostics.
        if value in {"YES", "NO"}:
            entry["last_result"] = value == "YES"
        return value

    if event_type == "ERROR":
        raise RuntimeError(f"Service {name} reader failed: {value}")

    if event_type == "EOF":
        return "EOF"

    return value


# =========================
# One-shot task management
# =========================


def _resolve_script(target):
    """Resolve a script path relative to the project root."""
    from pathlib import Path

    project_root = Path(__file__).resolve().parent.parent
    script_path = (project_root / target).resolve()

    if not script_path.is_relative_to(project_root):
        raise ValueError(f"Script path escapes project root: {target}")

    if not script_path.is_file():
        raise FileNotFoundError(f"Script not found: {script_path}")

    return script_path


def run_task(name, abbreviations, runtime, arguments=None):
    """Run a declared one-shot task, collect output, and return its exit code."""
    definition = abbreviations.get("actions", {}).get(name)
    if definition is None:
        raise ValueError(f"Unknown task/action: {name}")

    if definition.get("handler") != "run_task":
        raise ValueError(f"Action is not a one-shot task: {name}")

    script_path = _resolve_script(definition["target"])
    command = _build_command(
        script_path,
        arguments if arguments is not None else definition.get("arguments", []),
    )

    completed = subprocess.run(
        command,
        env={**os.environ, "PYTHONPATH": str(PROJECT_ROOT)},
        cwd=script_path.parent.parent,
        capture_output=True,
        text=True,
        check=False,
    )

    result = {
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }
    runtime["tasks"][name] = result
    return result


# =========================
# Process status and shutdown
# =========================

def get_process_status(name, runtime):
    """Return running, finished, failed, or unknown for a managed process."""
    entry = runtime["services"].get(name)

    if entry is not None:
        process = entry["process"]
    else:
        task = runtime["tasks"].get(name)
        if task is None:
            return "unknown"
        return "finished" if task["returncode"] == 0 else "failed"

    returncode = process.poll()
    if returncode is None:
        return "running"
    return "finished" if returncode == 0 else "failed"


def stop_service(name, abbreviations, runtime, timeout=3):
    """Request graceful service shutdown, then terminate if it refuses."""
    entry = runtime["services"].get(name)
    if entry is None:
        return

    process = entry["process"]
    if process.poll() is not None:
        return

    definition = abbreviations.get("services", {}).get(name, {})
    stop_command = definition.get("commands", {}).get("stop")

    if stop_command is not None:
        process.stdin.write(f"{stop_command}\n")
        process.stdin.flush()
        try:
            process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            process.terminate()
    else:
        process.terminate()

    try:
        process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()

    if process.stdin:
        process.stdin.close()
    if process.stdout:
        process.stdout.close()


def stop_all_services(abbreviations, runtime):
    """Stop every registered persistent service."""
    for name in list(runtime["services"]):
        stop_service(name, abbreviations, runtime)


def shutdown_runtime(abbreviations, runtime):
    """Perform centralized cleanup when route execution ends."""
    stop_all_services(abbreviations, runtime)




# =========================
# 4. Results and expectations
# =========================

def store_result(name, result, runtime):
    """Store the latest result for a service or task."""

    service = runtime["services"].get(name)

    if service is not None:
        service["last_result"] = result
        return

    runtime.setdefault("results", {})[name] = result


def get_result(name, runtime):
    """Retrieve the latest stored result, or None if no result exists."""

    service = runtime["services"].get(name)

    if service is not None:
        return service["last_result"]

    return runtime.get("results", {}).get(name)


def expect_result(name, expected, runtime):
    """Compare a stored result with the expected value; return True or False."""

    actual = get_result(name, runtime)
    return actual == expected


def wait_for_result(name, expected, runtime, timeout=None):
    """Wait until a service reports the expected result, or the timeout expires."""

    import time

    deadline = None if timeout is None else time.monotonic() + timeout

    while True:
        actual = get_result(name, runtime)

        if actual == expected:
            return True

        if deadline is not None:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return False
        else:
            remaining = None

        if name not in runtime["services"]:
            raise ValueError(
                f"Cannot wait for service events: {name} is not a service."
            )

        event = read_service_event(name, runtime, timeout=remaining)

        if event is None:
            return False

        if event == "EOF":
            raise RuntimeError(f"Service exited while waiting for {name}.")

        if event.startswith("ERROR"):
            raise RuntimeError(f"Service {name} reported: {event}")

        if event == "YES":
            store_result(name, True, runtime)
        elif event == "NO":
            store_result(name, False, runtime)


def evaluate_condition(condition, runtime):
    """Evaluate a structured result comparison or a logical combination."""

    if not isinstance(condition, dict):
        raise ValueError("A condition must be a JSON object.")

    if "result" in condition and "equals" in condition:
        return expect_result(
            condition["result"],
            condition["equals"],
            runtime,
        )

    if "not" in condition:
        return not evaluate_condition(condition["not"], runtime)

    if "all" in condition:
        return all(
            evaluate_condition(item, runtime)
            for item in condition["all"]
        )

    if "any" in condition:
        return any(
            evaluate_condition(item, runtime)
            for item in condition["any"]
        )

    raise ValueError(f"Unsupported condition: {condition}")



# =========================
# 5. Instruction execution
# =========================



def execute_instruction(instruction, abbreviations, coordinates, runtime):
    """Resolve one instruction and dispatch it to its handler."""
    resolved = resolve_instruction(instruction, abbreviations)

    name = resolved["name"]
    kind = resolved["kind"]
    arguments = resolve_arguments(resolved["arguments"], coordinates)

    if kind == "instruction":
        handlers = {
            "loop": execute_loop,
            "if": execute_condition,
            "expect": execute_expect,
            "wait": execute_wait,
            "exit": execute_exit,
            "sleep": execute_sleep,
            "while": execute_while,
        }

        handler_name = resolved["definition"].get("handler")
        handler = handlers.get(name)

        if handler is None or handler.__name__ != handler_name:
            raise ValueError(
                f"No valid execution handler configured for instruction: {name}"
            )

        return handler(arguments, abbreviations, coordinates, runtime)

    if kind == "action":
        return execute_action(
            name, arguments, resolved["definition"], abbreviations, runtime
        )

    raise ValueError(f"Unsupported instruction kind: {kind}")


def execute_sequence(sequence, abbreviations, coordinates, runtime):
    """Execute instructions in order until the sequence ends or exits."""
    if not isinstance(sequence, list):
        raise ValueError("A sequence must be a JSON list of instructions.")

    results = []

    for instruction in sequence:
        if runtime.get("route_exit", False):
            break

        result = execute_instruction(
            instruction, abbreviations, coordinates, runtime
        )
        results.append(result)

    return results


def execute_loop(arguments, abbreviations, coordinates, runtime):
    """Execute a body a fixed number of times or forever."""
    if not isinstance(arguments, dict):
        raise ValueError("Loop arguments must be an object.")

    count = arguments.get("count")
    body = arguments.get("do")

    if not isinstance(body, list):
        raise ValueError("A loop requires a 'do' list of instructions.")

    if count == "forever":
        while not runtime.get("route_exit", False):
            execute_sequence(body, abbreviations, coordinates, runtime)
        return

    if isinstance(count, bool) or not isinstance(count, int) or count < 1:
        raise ValueError("Loop count must be a positive integer or 'forever'.")

    for _ in range(count):
        if runtime.get("route_exit", False):
            break

        execute_sequence(body, abbreviations, coordinates, runtime)


def execute_condition(arguments, abbreviations, coordinates, runtime):
    """Evaluate a condition and execute the matching branch."""
    if not isinstance(arguments, dict):
        raise ValueError("Condition arguments must be an object.")

    if "condition" not in arguments:
        raise ValueError("An if instruction requires a 'condition'.")

    condition = evaluate_condition(arguments["condition"], runtime)

    if condition:
        branch = arguments.get("then", [])
    else:
        branch = arguments.get("else", [])

    return execute_sequence(branch, abbreviations, coordinates, runtime)


def execute_expect(arguments, abbreviations, coordinates, runtime):
    """Check that a stored result matches an expected value."""
    if not isinstance(arguments, dict):
        raise ValueError("Expect arguments must be an object.")

    if "result" not in arguments or "equals" not in arguments:
        raise ValueError("Expect requires 'result' and 'equals'.")

    if not expect_result(arguments["result"], arguments["equals"], runtime):
        raise RuntimeError(
            f"Expectation failed: {arguments['result']} "
            f"was expected to equal {arguments['equals']!r}."
        )

    return True

def execute_sleep(arguments, abbreviations, coordinates, runtime):
    if not isinstance(arguments, list) or len(arguments) != 1:
        raise ValueError("sleep expects one argument: seconds")

    seconds = arguments[0]

    if isinstance(seconds, bool) or not isinstance(seconds, (int, float)) or seconds < 0:
        raise ValueError("sleep duration must be a non-negative number")

    time.sleep(seconds)

def execute_while(arguments, abbreviations, coordinates, runtime):
    if not isinstance(arguments, dict):
        raise ValueError("while expects an object")

    condition = arguments.get("condition")
    sequence = arguments.get("do")

    if not isinstance(sequence, list):
        raise ValueError("while requires a 'do' list")

    while True:
        # Refresh results received from background services.
        for name in list(runtime["services"]):
            while True:
                event = read_service_event(name, runtime, timeout=0)
                if event is None:
                    break
                if event == "EOF":
                    break

        if runtime["route_exit"]:
            break

        if not evaluate_condition(condition, runtime):
            break

        execute_sequence(sequence, abbreviations, coordinates, runtime)

        time.sleep(0.1)


def execute_wait(arguments, abbreviations, coordinates, runtime):
    """Wait for a named result to match the expected value."""
    if not isinstance(arguments, dict):
        raise ValueError("Wait arguments must be an object.")

    if "result" not in arguments or "equals" not in arguments:
        raise ValueError("Wait requires 'result' and 'equals'.")

    timeout = arguments.get("timeout")

    matched = wait_for_result(
        arguments["result"],
        arguments["equals"],
        runtime,
        timeout=timeout,
    )

    if not matched:
        raise TimeoutError(
            f"Timed out waiting for {arguments['result']} "
            f"to equal {arguments['equals']!r}."
        )

    return True


def execute_action(name, arguments, definition, abbreviations, runtime):
    """Run an action through its configured task or service handler."""
    handler = definition.get("handler")

    if handler == "run_task":
        result = run_task(
            name,
            abbreviations,
            runtime,
            arguments=arguments,
        )

        store_result(name, result["stdout"], runtime)

        if result["returncode"] != 0:
            raise RuntimeError(
                f"Action '{name}' failed with exit code "
                f"{result['returncode']}: {result['stderr']}"
            )

        return result["stdout"]

    if handler == "service":
        start_service(name, abbreviations, runtime)
        return name

    raise ValueError(
        f"Unsupported action handler {handler!r} for action {name!r}."
    )


def execute_exit(arguments, abbreviations, coordinates, runtime):
    """Request route termination; manager.py handles cleanup."""
    runtime["route_exit"] = True
    return


# =========================
# 6. Error handling and cleanup
# =========================


def log_event(message, level="INFO"):
    """Print a consistently formatted runtime event."""
    from datetime import datetime

    timestamp = datetime.now().astimezone().isoformat(timespec="seconds")
    print(f"[{timestamp}] [{level}] {message}", flush=True)


def handle_task_failure(name, error, runtime):
    """Record a task failure and log its details."""
    runtime.setdefault("results", {})[name] = {
        "status": "failed",
        "error": str(error),
    }

    log_event(f"Task '{name}' failed: {error}", level="ERROR")


def handle_service_failure(name, error, runtime):
    """Record a service failure and log its details."""
    service = runtime.get("services", {}).get(name)

    if service is not None:
        service["last_result"] = {
            "status": "failed",
            "error": str(error),
        }

    runtime.setdefault("results", {})[name] = {
        "status": "failed",
        "error": str(error),
    }

    log_event(f"Service '{name}' failed: {error}", level="ERROR")

def create_runtime():
    return {
        "services": {},
        "tasks": {},
        "results": {},
        "route_exit": False,
    }


def shutdown_runtime(abbreviations, runtime):
    """Stop all running services and report cleanup failures."""
    log_event("Shutting down runtime.")

    try:
        stop_all_services(abbreviations, runtime)
    except Exception as error:
        log_event(
            f"Error while stopping services: {error}",
            level="ERROR",
        )
    finally:
        log_event("Runtime shutdown complete.")
