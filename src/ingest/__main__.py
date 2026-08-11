"""Allow `python -m src.ingest` to run the CLI entry point."""

from src.ingest.ingest import main

if __name__ == "__main__":
    main()
