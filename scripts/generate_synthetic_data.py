from __future__ import annotations

import argparse
import csv
import json
import random
import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Iterable

COUNTRIES = [
    ("US", "New York"),
    ("US", "Chicago"),
    ("US", "San Francisco"),
    ("US", "Miami"),
    ("CA", "Toronto"),
    ("GB", "London"),
    ("FR", "Paris"),
    ("DE", "Berlin"),
    ("BR", "Sao Paulo"),
    ("JP", "Tokyo"),
    ("SG", "Singapore"),
]
MERCHANT_CATEGORIES = [
    ("5411", "Grocery"),
    ("5812", "Restaurant"),
    ("5732", "Electronics"),
    ("5541", "Fuel"),
    ("5311", "Department Store"),
    ("4722", "Travel"),
    ("7995", "Gaming"),
    ("6011", "ATM"),
    ("4111", "Transit"),
]
FIRST_NAMES = ["Avery", "Jordan", "Taylor", "Morgan", "Riley", "Casey", "Jamie", "Quinn"]
LAST_NAMES = ["Patel", "Johnson", "Garcia", "Smith", "Brown", "Kim", "Nguyen", "Davis"]
DEVICE_TYPES = ["mobile", "desktop", "tablet"]
OPERATING_SYSTEMS = ["iOS", "Android", "Windows", "macOS", "Linux"]
CHANNELS = ["card_present", "card_not_present", "mobile_wallet", "atm"]
SCENARIOS = [
    "card_testing",
    "impossible_travel",
    "new_device_takeover",
    "transaction_velocity",
    "behavior_deviation",
    "merchant_fraud_burst",
]


@dataclass(frozen=True)
class CustomerProfile:
    customer_id: str
    account_id: str
    card_ids: list[str]
    device_ids: list[str]
    home_country: str
    home_city: str
    avg_amount: float


def stable_uuid(namespace: str, value: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"fraudops:{namespace}:{value}"))


def write_csv(output_dir: Path, name: str, rows: Iterable[dict]) -> int:
    rows = list(rows)
    if not rows:
        return 0
    path = output_dir / f"{name}.csv"
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    return len(rows)


def iso(dt: datetime) -> str:
    return dt.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def build_customers(rng: random.Random, count: int, start_at: datetime) -> tuple[list[dict], list[dict], list[dict], list[dict], list[CustomerProfile]]:
    customers: list[dict] = []
    accounts: list[dict] = []
    cards: list[dict] = []
    devices: list[dict] = []
    profiles: list[CustomerProfile] = []

    for idx in range(1, count + 1):
        external = f"CUST-{idx:06d}"
        customer_id = stable_uuid("customer", external)
        first = rng.choice(FIRST_NAMES)
        last = rng.choice(LAST_NAMES)
        country, city = rng.choice(COUNTRIES[:5])
        opened_at = start_at - timedelta(days=rng.randint(30, 1800))
        segment = rng.choices(["mass", "affluent", "small_business"], weights=[75, 20, 5])[0]
        risk_tier = rng.choices(["low", "standard", "elevated"], weights=[25, 65, 10])[0]
        avg_amount = round(rng.lognormvariate(3.35, 0.55), 2)

        customers.append(
            {
                "customer_id": customer_id,
                "customer_external_id": external,
                "full_name": f"{first} {last}",
                "email": f"{first.lower()}.{last.lower()}{idx}@example.com",
                "phone_number": f"+1555{idx:07d}",
                "home_country": country,
                "home_city": city,
                "customer_segment": segment,
                "risk_tier": risk_tier,
                "opened_at": iso(opened_at),
            }
        )

        account_external = f"ACCT-{idx:06d}"
        account_id = stable_uuid("account", account_external)
        accounts.append(
            {
                "account_id": account_id,
                "customer_id": customer_id,
                "account_external_id": account_external,
                "account_type": rng.choices(["checking", "credit_card", "savings"], weights=[45, 45, 10])[0],
                "currency": "USD",
                "opened_at": iso(opened_at + timedelta(days=rng.randint(0, 30))),
                "status": "active",
            }
        )

        customer_card_ids: list[str] = []
        for card_idx in range(rng.choices([1, 2], weights=[70, 30])[0]):
            card_external = f"CARD-{idx:06d}-{card_idx + 1}"
            card_id = stable_uuid("card", card_external)
            customer_card_ids.append(card_id)
            cards.append(
                {
                    "card_id": card_id,
                    "account_id": account_id,
                    "card_external_id": card_external,
                    "card_network": rng.choice(["Visa", "Mastercard", "Amex"]),
                    "last_four": f"{rng.randint(0, 9999):04d}",
                    "issued_at": iso(opened_at + timedelta(days=rng.randint(1, 60))),
                    "expires_at": (date.today().replace(year=date.today().year + rng.randint(1, 5))).isoformat(),
                    "status": "active",
                }
            )

        customer_device_ids: list[str] = []
        for device_idx in range(rng.choices([1, 2, 3], weights=[55, 35, 10])[0]):
            device_external = f"DEV-{idx:06d}-{device_idx + 1}"
            device_id = stable_uuid("device", device_external)
            customer_device_ids.append(device_id)
            devices.append(
                {
                    "device_id": device_id,
                    "customer_id": customer_id,
                    "device_external_id": device_external,
                    "device_type": rng.choice(DEVICE_TYPES),
                    "operating_system": rng.choice(OPERATING_SYSTEMS),
                    "first_seen_at": iso(opened_at + timedelta(days=rng.randint(1, 120))),
                    "trusted": rng.choice([True, True, True, False]),
                }
            )

        profiles.append(
            CustomerProfile(
                customer_id=customer_id,
                account_id=account_id,
                card_ids=customer_card_ids,
                device_ids=customer_device_ids,
                home_country=country,
                home_city=city,
                avg_amount=avg_amount,
            )
        )

    return customers, accounts, cards, devices, profiles


def build_merchants(rng: random.Random, count: int) -> list[dict]:
    merchants: list[dict] = []
    for idx in range(1, count + 1):
        external = f"MERCH-{idx:05d}"
        country, city = rng.choice(COUNTRIES)
        mcc, category = rng.choice(MERCHANT_CATEGORIES)
        merchants.append(
            {
                "merchant_id": stable_uuid("merchant", external),
                "merchant_external_id": external,
                "merchant_name": f"{category} Merchant {idx:05d}",
                "merchant_category_code": mcc,
                "merchant_category": category,
                "country": country,
                "city": city,
                "risk_tier": rng.choices(["low", "standard", "elevated"], weights=[30, 60, 10])[0],
            }
        )
    return merchants


def choose_label_dates(rng: random.Random, transaction_at: datetime, is_fraud: bool, is_false_positive: bool) -> tuple[str, str, str, str, str]:
    if is_false_positive:
        confirmed = transaction_at + timedelta(hours=rng.randint(2, 48))
        return "legitimate", "analyst_review", iso(confirmed), "", iso(confirmed)
    if is_fraud:
        delay_days = rng.randint(5, 21)
        available = transaction_at + timedelta(days=delay_days)
        return "fraud", "chargeback", iso(available), available.date().isoformat(), iso(available + timedelta(hours=4))
    if rng.random() < 0.08:
        available = transaction_at + timedelta(days=rng.randint(1, 10))
        return "legitimate", "customer_confirmation", iso(available), "", ""
    return "unknown", "", "", "", ""


def build_transactions(
    rng: random.Random,
    profiles: list[CustomerProfile],
    merchants: list[dict],
    count: int,
    start_at: datetime,
    days: int,
    fraud_rate: float,
) -> tuple[list[dict], list[dict]]:
    rows: list[dict] = []
    extra_devices: list[dict] = []
    burst_merchants = rng.sample(merchants, k=max(1, min(5, len(merchants))))
    scenario_budget = max(1, int(count * fraud_rate))
    scenario_positions = set(rng.sample(range(count), k=scenario_budget))
    normal_travel_positions = set(rng.sample([i for i in range(count) if i not in scenario_positions], k=max(1, count // 100)))

    for idx in range(count):
        profile = rng.choice(profiles)
        transaction_at = start_at + timedelta(minutes=rng.randint(0, days * 24 * 60))
        scenario = ""
        is_fraud = False
        false_positive = False
        merchant = rng.choice(merchants)
        country = profile.home_country
        city = profile.home_city
        amount = max(1.0, rng.lognormvariate(3.2, 0.65) * (profile.avg_amount / 30.0))
        channel = rng.choice(CHANNELS)
        device_id = rng.choice(profile.device_ids)

        if idx in scenario_positions:
            scenario = rng.choice(SCENARIOS)
            is_fraud = True
            if scenario == "card_testing":
                amount = rng.choice([1.01, 2.49, 3.99, rng.uniform(450, 2200)])
                channel = "card_not_present"
            elif scenario == "impossible_travel":
                country, city = rng.choice([place for place in COUNTRIES if place[0] != profile.home_country])
                amount *= rng.uniform(2.0, 6.0)
            elif scenario == "new_device_takeover":
                device_external = f"DEV-NEW-{idx + 1:09d}"
                device_id = stable_uuid("device", device_external)
                extra_devices.append(
                    {
                        "device_id": device_id,
                        "customer_id": profile.customer_id,
                        "device_external_id": device_external,
                        "device_type": rng.choice(DEVICE_TYPES),
                        "operating_system": rng.choice(OPERATING_SYSTEMS),
                        "first_seen_at": iso(transaction_at - timedelta(minutes=rng.randint(1, 20))),
                        "trusted": False,
                    }
                )
                amount *= rng.uniform(4.0, 10.0)
                channel = "card_not_present"
            elif scenario == "transaction_velocity":
                amount *= rng.uniform(1.2, 3.0)
            elif scenario == "behavior_deviation":
                amount = profile.avg_amount * rng.uniform(8.0, 20.0)
            elif scenario == "merchant_fraud_burst":
                merchant = rng.choice(burst_merchants)
                amount *= rng.uniform(2.5, 8.0)
        elif idx in normal_travel_positions:
            scenario = "normal_travel_false_positive"
            false_positive = True
            country, city = rng.choice([place for place in COUNTRIES if place[0] != profile.home_country])
            amount *= rng.uniform(1.5, 4.0)
            channel = rng.choice(["card_present", "mobile_wallet"])
        else:
            country, city = (merchant["country"], merchant["city"]) if rng.random() < 0.18 else (profile.home_country, profile.home_city)

        label, source, available_at, chargeback_date, analyst_confirmed_at = choose_label_dates(
            rng, transaction_at, is_fraud, false_positive
        )
        external = f"TXN-{idx + 1:09d}"
        rows.append(
            {
                "transaction_id": stable_uuid("transaction", external),
                "transaction_external_id": external,
                "customer_id": profile.customer_id,
                "account_id": profile.account_id,
                "card_id": rng.choice(profile.card_ids),
                "device_id": device_id,
                "merchant_id": merchant["merchant_id"],
                "transaction_at": iso(transaction_at),
                "amount": f"{amount:.2f}",
                "currency": "USD",
                "merchant_country": country,
                "merchant_city": city,
                "channel": channel,
                "status": rng.choices(["AUTHORIZED", "DECLINED", "REVERSED", "SETTLED"], weights=[70, 8, 2, 20])[0],
                "authorization_code": f"AUTH{rng.randint(100000, 999999)}",
                "fraud_label": label,
                "label_source": source,
                "label_available_at": available_at,
                "chargeback_date": chargeback_date,
                "analyst_confirmed_at": analyst_confirmed_at,
                "fraud_scenario": scenario,
            }
        )
    return rows, extra_devices


def build_reference_rows(start_at: datetime) -> dict[str, list[dict]]:
    rule_rows = [
        ("CARD_TESTING", "Card testing", "Small test charges followed by a larger transaction", "high"),
        ("IMPOSSIBLE_TRAVEL", "Impossible travel", "Country change is unrealistic for the time window", "high"),
        ("NEW_DEVICE_HIGH_VALUE", "New device high value", "New device attempts an unusually high amount", "medium"),
        ("VELOCITY", "Transaction velocity", "Several transactions occur in a short interval", "medium"),
        ("BEHAVIOR_DEVIATION", "Behavior deviation", "Amount is far above the customer baseline", "medium"),
        ("MERCHANT_BURST", "Merchant fraud burst", "Merchant receives clustered fraud reports", "high"),
    ]
    return {
        "fraud_rule": [
            {
                "fraud_rule_id": stable_uuid("fraud_rule", code),
                "rule_code": code,
                "rule_name": name,
                "description": description,
                "severity": severity,
                "active": True,
            }
            for code, name, description, severity in rule_rows
        ],
        "threshold_configuration": [
            {
                "threshold_configuration_id": stable_uuid("threshold_configuration", "baseline-v1"),
                "configuration_name": "baseline-v1",
                "step_up_threshold": "0.35000",
                "manual_review_threshold": "0.65000",
                "hold_decline_threshold": "0.90000",
                "effective_from": iso(start_at),
                "effective_to": "",
            }
        ],
        "model_version": [
            {
                "model_version_id": stable_uuid("model_version", "rules-baseline-v0"),
                "model_name": "fraud-risk-model",
                "version_label": "rules-baseline-v0",
                "training_started_at": "",
                "training_completed_at": "",
                "metrics": json.dumps({"note": "placeholder before ML phase"}),
                "artifact_uri": "",
                "promoted": False,
            }
        ],
        "data_quality_rule": [
            {
                "data_quality_rule_id": stable_uuid("data_quality_rule", "TXN_AMOUNT_POSITIVE"),
                "rule_code": "TXN_AMOUNT_POSITIVE",
                "table_name": "transaction",
                "column_name": "amount",
                "description": "Transaction amount must be positive",
                "severity": "critical",
                "active": True,
            },
            {
                "data_quality_rule_id": stable_uuid("data_quality_rule", "TXN_CUSTOMER_PRESENT"),
                "rule_code": "TXN_CUSTOMER_PRESENT",
                "table_name": "transaction",
                "column_name": "customer_id",
                "description": "Transaction must reference an existing customer",
                "severity": "critical",
                "active": True,
            },
        ],
    }


def load_to_postgres(output_dir: Path) -> None:
    try:
        import psycopg
    except ImportError as exc:
        raise SystemExit("Install psycopg first: pip install 'psycopg[binary]'") from exc

    import os

    conninfo = os.getenv(
        "DATABASE_URL_PG",
        "postgresql://fraudops_user:fraudops_password@localhost:55433/fraudops",
    )
    load_order = [
        "customer",
        "account",
        "card",
        "device",
        "merchant",
        "transaction",
        "fraud_rule",
        "threshold_configuration",
        "model_version",
        "data_quality_rule",
    ]
    with psycopg.connect(conninfo) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SET search_path TO fraudops")
            for table in load_order:
                path = output_dir / f"{table}.csv"
                if not path.exists():
                    continue
                with path.open("r", encoding="utf-8") as handle:
                    header = handle.readline().strip().split(",")
                    columns = ", ".join(header)
                    with cursor.copy(f"COPY {table} ({columns}) FROM STDIN WITH CSV") as copy:
                        for line in handle:
                            copy.write(line)
        connection.commit()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate reproducible synthetic FraudOps data.")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--customers", type=int, default=500)
    parser.add_argument("--merchants", type=int, default=200)
    parser.add_argument("--transactions", type=int, default=10_000)
    parser.add_argument("--days", type=int, default=60)
    parser.add_argument("--fraud-rate", type=float, default=0.02)
    parser.add_argument("--output-dir", type=Path, default=Path("data/sample"))
    parser.add_argument("--load-db", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not 0 < args.fraud_rate < 0.2:
        raise SystemExit("--fraud-rate should be between 0 and 0.2 for this simulator")

    rng = random.Random(args.seed)
    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    start_at = datetime.now(UTC) - timedelta(days=args.days)

    customers, accounts, cards, devices, profiles = build_customers(rng, args.customers, start_at)
    merchants = build_merchants(rng, args.merchants)
    transactions, new_devices = build_transactions(
        rng=rng,
        profiles=profiles,
        merchants=merchants,
        count=args.transactions,
        start_at=start_at,
        days=args.days,
        fraud_rate=args.fraud_rate,
    )
    devices.extend(new_devices)
    references = build_reference_rows(start_at)

    counts = {
        "customer": write_csv(output_dir, "customer", customers),
        "account": write_csv(output_dir, "account", accounts),
        "card": write_csv(output_dir, "card", cards),
        "device": write_csv(output_dir, "device", devices),
        "merchant": write_csv(output_dir, "merchant", merchants),
        "transaction": write_csv(output_dir, "transaction", transactions),
    }
    for name, rows in references.items():
        counts[name] = write_csv(output_dir, name, rows)

    fraud_count = sum(1 for row in transactions if row["fraud_label"] == "fraud")
    false_positive_count = sum(1 for row in transactions if row["fraud_scenario"] == "normal_travel_false_positive")
    summary = {
        "seed": args.seed,
        "output_dir": str(output_dir),
        "counts": counts,
        "fraud_transactions": fraud_count,
        "fraud_rate_observed": round(fraud_count / max(1, len(transactions)), 4),
        "normal_travel_false_positives": false_positive_count,
        "scenarios": sorted({row["fraud_scenario"] for row in transactions if row["fraud_scenario"]}),
    }
    (output_dir / "generation_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    if args.load_db:
        load_to_postgres(output_dir)

    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()

