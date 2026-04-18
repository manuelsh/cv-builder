"""Command-line interface for CV Builder."""

import argparse
import asyncio
import sys

from src.orchestrator import PipelineOrchestrator
from src.llm.config import (
    get_backend_name,
    load_config,
    validate_backend_prerequisites,
)


def create_parser() -> argparse.ArgumentParser:
    """Create the argument parser.

    Returns:
        Configured argument parser.
    """
    parser = argparse.ArgumentParser(
        prog="cv-builder",
        description="Multi-agent system for generating personalized CVs",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # Generate subcommand
    generate_parser = subparsers.add_parser(
        "generate",
        help="Generate a CV for a job target",
    )
    _add_generate_arguments(generate_parser)

    # Validate subcommand
    validate_parser = subparsers.add_parser(
        "validate",
        help="Validate configuration",
    )
    validate_parser.add_argument(
        "--config",
        "-c",
        type=str,
        default="config.yaml",
        help="Path to config file",
    )
    validate_parser.add_argument(
        "--llm-backend",
        choices=["litellm", "codex-sdk"],
        help="LLM backend to validate",
    )

    # Auth subcommand
    auth_parser = subparsers.add_parser(
        "auth",
        help="Authenticate with Google Drive",
    )
    auth_parser.add_argument(
        "--status",
        action="store_true",
        help="Check authentication status",
    )

    return parser


def _add_generate_arguments(parser: argparse.ArgumentParser) -> None:
    """Add arguments for the generate subcommand."""
    parser.add_argument(
        "job_target",
        type=str,
        help="Job URL, file path, or description",
    )

    parser.add_argument(
        "--config",
        "-c",
        type=str,
        default="config.yaml",
        help="Path to config file (default: config.yaml)",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print CV content without creating Google Doc",
    )

    parser.add_argument(
        "--style",
        type=str,
        choices=["formal", "modern", "creative", "technical"],
        help="Override config style",
    )

    parser.add_argument(
        "--language",
        type=str,
        help="Override config language (e.g., en, es, de)",
    )

    parser.add_argument(
        "--max-pages",
        type=int,
        choices=[1, 2, 3],
        help="Override config max pages",
    )
    parser.add_argument(
        "--llm-backend",
        choices=["litellm", "codex-sdk"],
        help="LLM backend to use",
    )


def main() -> int:
    """Main entry point.

    Returns:
        Exit code.
    """
    parser = create_parser()
    args = parser.parse_args()

    if args.command == "generate":
        return asyncio.run(run_generate(args))
    elif args.command == "validate":
        return run_validate(args)
    elif args.command == "auth":
        return run_auth(args)

    return 1


async def run_generate(args: argparse.Namespace) -> int:
    """Run the generate command.

    Args:
        args: Parsed arguments.

    Returns:
        Exit code.
    """
    try:
        llm_config = load_config(
            {"llm_backend": args.llm_backend} if args.llm_backend else None
        )
        orchestrator = PipelineOrchestrator(llm_config=llm_config)
        result = await orchestrator.generate_cv(
            job_target=args.job_target,
            config_path=args.config,
            dry_run=args.dry_run,
            style_override=args.style,
            language_override=args.language,
            max_pages_override=args.max_pages,
        )

        if args.dry_run:
            print("\n--- CV Content (JSON) ---\n")
            print(result.model_dump_json(indent=2))

        return 0

    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def run_validate(args: argparse.Namespace) -> int:
    """Run the validate command.

    Args:
        args: Parsed arguments.

    Returns:
        Exit code.
    """
    from src.agents.config_reader import ConfigReaderAgent

    try:
        llm_config = load_config(
            {"llm_backend": args.llm_backend} if args.llm_backend else None
        )
        backend_name = get_backend_name(config=llm_config)

        agent = ConfigReaderAgent(config=llm_config)
        config = agent.run(args.config)
        errors, warnings = validate_backend_prerequisites(
            backend_name=backend_name,
            config=llm_config,
        )

        if errors:
            print("Configuration validation failed:", file=sys.stderr)
            for error in errors:
                print(f"  - {error}", file=sys.stderr)
            return 1

        print("Configuration is valid!")
        print(f"  Source folders: {len(config.source_folders)}")
        print(f"  Output folder: {config.output_folder or '(first source folder)'}")
        print(f"  Style: {config.style}")
        print(f"  Template: {config.template}")
        print(f"  Language: {config.language}")
        print(f"  Max pages: {config.max_pages}")
        print(f"  LLM backend: {backend_name}")
        print("  Backend prerequisites: OK")

        for warning in warnings:
            print(f"  Warning: {warning}")

        return 0

    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def run_auth(args: argparse.Namespace) -> int:
    """Run the auth command.

    Args:
        args: Parsed arguments.

    Returns:
        Exit code.
    """
    from src.google_drive.auth import get_credentials, TOKEN_PATH

    if args.status:
        if TOKEN_PATH.exists():
            print(f"Authenticated. Token stored at: {TOKEN_PATH}")
            return 0
        else:
            print("Not authenticated. Run 'cv-builder auth' to authenticate.")
            return 1

    try:
        get_credentials()
        print("Authentication successful!")
        print(f"Token stored at: {TOKEN_PATH}")
        return 0
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Authentication failed: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
