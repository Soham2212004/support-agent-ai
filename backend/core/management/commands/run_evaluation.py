"""Scores a pipeline (baseline or enhanced) against a JSON question dataset for one account.

Usage:
  python manage.py run_evaluation --account-email you@example.com --dataset backend/evaluation/datasets/sample.json --pipeline baseline
  python manage.py run_evaluation --account-email you@example.com --dataset backend/evaluation/datasets/sample.json --pipeline enhanced --compare-with evaluation/results/baseline-....json

Uses the "fake" (no-AI) provider by default, matching the spec's "no real LLM in automated
evaluation" guidance and costing nothing. Pass --provider to use a real configured provider.
"""
import json
import time
from datetime import datetime
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from core import llm, rag
from core.evaluation import correct_decline, retrieval_hit, summarize
from core.models import BotSettings, ClientAccount, ClientDocument


class Command(BaseCommand):
    help = "Run the evaluation harness against a dataset for one account's knowledge base."

    def add_arguments(self, parser):
        parser.add_argument("--account-email", required=True)
        parser.add_argument("--dataset", required=True)
        parser.add_argument("--pipeline", choices=["baseline", "enhanced"], default="baseline")
        parser.add_argument("--provider", default="fake")
        parser.add_argument("--output-dir", default="evaluation/results")
        parser.add_argument("--compare-with", default=None, help="Path to a previous run's JSON result to compare against")

    def handle(self, *args, **options):
        account = ClientAccount.objects.filter(email=options["account_email"]).first()
        if account is None:
            raise CommandError(f"No account found for {options['account_email']}")

        dataset_path = Path(options["dataset"])
        if not dataset_path.exists():
            raise CommandError(f"Dataset not found: {dataset_path}")
        questions = json.loads(dataset_path.read_text())

        document = ClientDocument.objects.filter(account=account).first()
        bot_settings = BotSettings.get_for_account(account)
        bot_settings.pipeline = options["pipeline"]  # evaluate as this pipeline, without mutating the saved setting

        provider = llm.get_provider(options["provider"])

        rows = []
        for item in questions:
            started = time.monotonic()
            passages = rag.retrieve(account, document, item["question"])
            full_text = ""
            is_fallback = False
            tokens_in = tokens_out = 0

            for event in rag.stream_answer(account, document, [], item["question"], provider, bot_settings_override=bot_settings):
                if event["type"] == "token":
                    full_text += event["text"]
                elif event["type"] == "final":
                    full_text = event["text"] or full_text
                    is_fallback = event["is_fallback"]
                    tokens_in, tokens_out = event["tokens_in"], event["tokens_out"]

            latency_ms = (time.monotonic() - started) * 1000
            rows.append(
                {
                    "question": item["question"],
                    "category": item.get("category", ""),
                    "answer": full_text,
                    "is_fallback": is_fallback,
                    "retrieval_hit": retrieval_hit(item.get("expected_source", ""), passages),
                    "correct_decline": correct_decline(item.get("answerable", True), is_fallback),
                    "latency_ms": round(latency_ms, 1),
                    "tokens_in": tokens_in,
                    "tokens_out": tokens_out,
                }
            )
            self.stdout.write(f"  {item['question'][:60]:60s} -> fallback={is_fallback} ({latency_ms:.0f}ms)")

        result = {
            "pipeline": options["pipeline"],
            "provider": provider["id"],
            "account_email": account.email,
            "run_at": datetime.utcnow().isoformat(),
            "summary": summarize(rows),
            "rows": rows,
        }

        out_dir = Path(options["output_dir"])
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"{options['pipeline']}-{datetime.utcnow():%Y%m%d-%H%M%S}.json"
        out_path.write_text(json.dumps(result, indent=2))
        self.stdout.write(self.style.SUCCESS(f"\nSaved: {out_path}"))
        self._print_table(result["summary"], title=options["pipeline"])

        if options["compare_with"]:
            other = json.loads(Path(options["compare_with"]).read_text())
            self._print_comparison(other, result)

    def _print_table(self, summary, title):
        self.stdout.write(f"\n--- {title} ---")
        for key, value in summary.items():
            self.stdout.write(f"  {key}: {value}")

    def _print_comparison(self, baseline_result, enhanced_result):
        md = ["| Metric | Baseline | Enhanced |", "|---|---|---|"]
        b, e = baseline_result["summary"], enhanced_result["summary"]
        for key in b:
            md.append(f"| {key} | {b.get(key)} | {e.get(key)} |")
        table = "\n".join(md)
        self.stdout.write("\n" + table)
        comparison_path = Path(enhanced_result.get("output_dir", "evaluation/results")) / "comparison.md" if False else Path("evaluation/results/comparison.md")
        comparison_path.parent.mkdir(parents=True, exist_ok=True)
        comparison_path.write_text(table)
        self.stdout.write(self.style.SUCCESS(f"\nComparison table saved: {comparison_path}"))