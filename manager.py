

"""Entry point for the generic JSON route manager."""

import argparse
import sys

from functions.manager_functions import (
    create_runtime,
    load_route,
    load_abbreviations,
    validate_route,
    execute_sequence,
    start_service,
    send_service_command,
    shutdown_runtime,
    log_event,
)


def parse_arguments():
    """Read the strategy name from the command line."""
    parser = argparse.ArgumentParser(
        description="Execute a JSON automation strategy."
    )

    parser.add_argument(
        "strategy",
        nargs="?",
        default="strategy1",
        help="Strategy name or JSON filename (default: strategy1)",
    )

    return parser.parse_args()


def start_route_services(route, abbreviations, runtime):
    """Start and enable every service declared by the route."""
    services = route.get("services", [])

    if not isinstance(services, list):
        raise ValueError("The route's 'services' field must be a list.")

    for name in services:
        if not isinstance(name, str):
            raise ValueError(f"Invalid service name: {name!r}")

        log_event(f"Starting service: {name}")
        start_service(name, abbreviations, runtime)

        service_definition = (
            abbreviations.get("services", {}).get(name, {})
        )
        commands = service_definition.get("commands", {})

        if "enable" in commands:
            send_service_command(
                name,
                "enable",
                abbreviations,
                runtime,
            )


def main():
    """Load configuration, execute a route, and clean up."""
    arguments = parse_arguments()
    runtime = create_runtime()
    abbreviations = {}
    exit_code = 0

    try:
        log_event(f"Loading strategy: {arguments.strategy}")

        route = load_route(arguments.strategy)
        abbreviations = load_abbreviations()

        validate_route(route)

        if not isinstance(route, dict):
            raise ValueError("The route's root must be a JSON object.")

        if not isinstance(route.get("sequence"), list):
            raise ValueError("The route must contain a 'sequence' list.")

        coordinates = {}

        log_event("Configuration loaded successfully.")

        start_route_services(route, abbreviations, runtime)

        log_event("Beginning route execution.")

        execute_sequence(
            route["sequence"],
            abbreviations,
            coordinates,
            runtime,
        )

        log_event("Route execution finished.")

    except KeyboardInterrupt:
        log_event("Interrupted by user.", level="WARNING")
        exit_code = 130

    except Exception as error:
        log_event(f"Route failed: {error}", level="ERROR")
        exit_code = 1

    finally:
        try:
            shutdown_runtime(abbreviations, runtime)
        except Exception as error:
            log_event(
                f"Runtime cleanup failed: {error}",
                level="ERROR",
            )
            exit_code = 1

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
