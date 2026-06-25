"""
CartSaver — CLI Entry Point
Usage:
    python -m cartsaver.main --setup            # Create tables + seed data
    python -m cartsaver.main --run-now          # Run the pipeline once
    python -m cartsaver.main --simulate         # Simulate random conversions
    python -m cartsaver.main --export           # Export CSVs for Power BI
    python -m cartsaver.main --start-scheduler  # Start daily 9 AM scheduler
    python -m cartsaver.main --all              # setup → run → simulate → export
"""

import argparse
import logging
import sys

# ---------------------------------------------------------------------------
# Logging configuration — set up before importing submodules that log
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)-36s | %(levelname)-7s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("cartsaver")


def cmd_setup():
    from cartsaver.db.setup import run_setup
    logger.info(">> Setting up database...")
    run_setup()
    logger.info("[OK] Database ready.")


def cmd_run():
    from cartsaver.scheduler.pipeline import run_pipeline
    logger.info(">> Running retention pipeline...")
    offers = run_pipeline()
    logger.info("[OK] Pipeline complete -- %d offers processed.", len(offers))


def cmd_simulate():
    from cartsaver.scheduler.pipeline import simulate_conversions
    logger.info(">> Simulating conversions...")
    simulate_conversions()
    logger.info("[OK] Conversion simulation done.")


def cmd_export():
    from cartsaver.analysis.funnel import run_funnel_analysis
    from cartsaver.segmentation.segment import segment_users
    from cartsaver.exports.export import run_all_exports

    logger.info(">> Exporting CSVs...")
    funnel = run_funnel_analysis()
    segmented = segment_users(funnel["user_summaries"])
    paths = run_all_exports(
        stage_counts=funnel["stage_counts"],
        dropoffs=funnel["dropoffs"],
        segmented_users=segmented,
    )
    for p in paths:
        logger.info("  -> %s", p)
    logger.info("[OK] Export complete.")


def cmd_scheduler():
    from cartsaver.scheduler.pipeline import start_scheduler
    logger.info(">> Starting scheduler (Ctrl+C to stop)...")
    start_scheduler()


def main():
    parser = argparse.ArgumentParser(
        prog="cartsaver",
        description="CartSaver -- Customer Retention & AI Automation Platform",
    )
    parser.add_argument("--setup",            action="store_true",
                        help="Create tables and seed dummy data")
    parser.add_argument("--run-now",          action="store_true",
                        help="Run the retention pipeline once")
    parser.add_argument("--simulate",         action="store_true",
                        help="Simulate random conversions")
    parser.add_argument("--export",           action="store_true",
                        help="Export CSV files for Power BI")
    parser.add_argument("--start-scheduler",  action="store_true",
                        help="Start daily APScheduler")
    parser.add_argument("--all",              action="store_true",
                        help="Run setup -> pipeline -> simulate -> export")

    args = parser.parse_args()

    if not any(vars(args).values()):
        parser.print_help()
        sys.exit(0)

    if args.all or args.setup:
        cmd_setup()
    if args.all or args.run_now:
        cmd_run()
    if args.all or args.simulate:
        cmd_simulate()
    if args.all or args.export:
        cmd_export()
    if args.start_scheduler:
        cmd_scheduler()


if __name__ == "__main__":
    main()
