from __future__ import annotations

import math

import pandas as pd

COUNTRY_COORDS = {
    "US": (39.8283, -98.5795),
    "CA": (56.1304, -106.3468),
    "GB": (55.3781, -3.4360),
    "FR": (46.2276, 2.2137),
    "DE": (51.1657, 10.4515),
    "BR": (-14.2350, -51.9253),
    "JP": (36.2048, 138.2529),
    "SG": (1.3521, 103.8198),
}

FEATURE_COLUMNS = [
    "transaction_id",
    "transaction_external_id",
    "customer_id",
    "account_id",
    "card_id",
    "device_id",
    "merchant_id",
    "transaction_at",
    "fraud_label",
    "fraud_scenario",
    "feature_pipeline_run_id",
    "transaction_amount",
    "transaction_hour",
    "is_weekend",
    "is_card_present",
    "is_international",
    "is_new_device",
    "is_new_merchant",
    "ip_country_mismatch",
    "customer_avg_amount_7d",
    "customer_avg_amount_30d",
    "amount_to_customer_avg_ratio",
    "transactions_last_10m",
    "transactions_last_1h",
    "amount_last_24h",
    "unique_countries_last_7d",
    "time_since_previous_transaction",
    "distance_from_previous_transaction",
    "failed_attempts_last_24h",
    "device_age_days",
    "customers_on_device_30d",
    "cards_on_device_30d",
    "device_transaction_velocity",
    "device_fraud_rate_history",
    "merchant_transaction_count_30d",
    "merchant_fraud_rate_30d",
    "merchant_chargeback_rate",
    "merchant_category_risk",
]


def haversine_km(country_a: str, country_b: str) -> float | None:
    if not country_a or not country_b or country_a not in COUNTRY_COORDS or country_b not in COUNTRY_COORDS:
        return None
    lat1, lon1 = COUNTRY_COORDS[country_a]
    lat2, lon2 = COUNTRY_COORDS[country_b]
    radius_km = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    value = math.sin(delta_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
    return 2 * radius_km * math.atan2(math.sqrt(value), math.sqrt(1 - value))


def _rolling_customer_features(group: pd.DataFrame) -> pd.DataFrame:
    group = group.sort_values("transaction_at").copy()
    indexed_amount = group.set_index("transaction_at")["amount"]
    declined = group.set_index("transaction_at")["status"].eq("DECLINED").astype(int)

    group["customer_avg_amount_7d"] = indexed_amount.rolling("7D", closed="left").mean().to_numpy()
    group["customer_avg_amount_30d"] = indexed_amount.rolling("30D", closed="left").mean().to_numpy()
    group["transactions_last_10m"] = indexed_amount.rolling("10min", closed="left").count().to_numpy()
    group["transactions_last_1h"] = indexed_amount.rolling("1h", closed="left").count().to_numpy()
    group["amount_last_24h"] = indexed_amount.rolling("24h", closed="left").sum().to_numpy()
    group["failed_attempts_last_24h"] = declined.rolling("24h", closed="left").sum().to_numpy()
    group["time_since_previous_transaction"] = group["transaction_at"].diff().dt.total_seconds().div(60)
    previous_country = group["merchant_country"].shift(1)
    group["distance_from_previous_transaction"] = [
        haversine_km(prev, current) for prev, current in zip(previous_country, group["merchant_country"], strict=False)
    ]

    unique_country_counts = []
    timestamps = group["transaction_at"].tolist()
    countries = group["merchant_country"].tolist()
    for idx, timestamp in enumerate(timestamps):
        lower = timestamp - pd.Timedelta(days=7)
        previous = [countries[pos] for pos, prior_time in enumerate(timestamps[:idx]) if lower <= prior_time < timestamp]
        unique_country_counts.append(len(set(previous)))
    group["unique_countries_last_7d"] = unique_country_counts
    return group


def _rolling_device_features(group: pd.DataFrame) -> pd.DataFrame:
    group = group.sort_values("transaction_at").copy()
    indexed_amount = group.set_index("transaction_at")["amount"]
    fraud_known = group.set_index("transaction_at")["fraud_label"].eq("fraud").astype(int)
    group["device_transaction_velocity"] = indexed_amount.rolling("1h", closed="left").count().to_numpy()
    group["device_fraud_rate_history"] = fraud_known.expanding().mean().shift(1).to_numpy()

    customer_counts = []
    card_counts = []
    timestamps = group["transaction_at"].tolist()
    customer_ids = group["customer_id"].tolist()
    card_ids = group["card_id"].tolist()
    for idx, timestamp in enumerate(timestamps):
        lower = timestamp - pd.Timedelta(days=30)
        prior_positions = [pos for pos, prior_time in enumerate(timestamps[:idx]) if lower <= prior_time < timestamp]
        customer_counts.append(len({customer_ids[pos] for pos in prior_positions}))
        card_counts.append(len({card_ids[pos] for pos in prior_positions}))
    group["customers_on_device_30d"] = customer_counts
    group["cards_on_device_30d"] = card_counts
    return group


def _rolling_merchant_features(group: pd.DataFrame) -> pd.DataFrame:
    group = group.sort_values("transaction_at").copy()
    indexed_amount = group.set_index("transaction_at")["amount"]
    fraud_known = group.set_index("transaction_at")["fraud_label"].eq("fraud").astype(int)
    chargeback = group.set_index("transaction_at")["label_source"].eq("chargeback").astype(int)
    group["merchant_transaction_count_30d"] = indexed_amount.rolling("30D", closed="left").count().to_numpy()
    group["merchant_fraud_rate_30d"] = fraud_known.rolling("30D", closed="left").mean().to_numpy()
    group["merchant_chargeback_rate"] = chargeback.expanding().mean().shift(1).to_numpy()
    return group


def _rolling_category_risk(group: pd.DataFrame) -> pd.DataFrame:
    group = group.sort_values("transaction_at").copy()
    fraud_known = group["fraud_label"].eq("fraud").astype(int)
    group["merchant_category_risk"] = fraud_known.expanding().mean().shift(1)
    return group


def build_point_in_time_features(
    transactions: pd.DataFrame,
    customers: pd.DataFrame,
    devices: pd.DataFrame,
    merchants: pd.DataFrame,
    pipeline_run_id: str,
) -> pd.DataFrame:
    """Build leakage-safe features using only records earlier than each transaction."""
    frame = transactions.copy()
    frame["transaction_at"] = pd.to_datetime(frame["transaction_at"], utc=True, errors="coerce")
    frame["amount"] = pd.to_numeric(frame["amount"], errors="coerce")
    if "label_source" not in frame.columns:
        frame["label_source"] = ""
    if "fraud_scenario" not in frame.columns:
        frame["fraud_scenario"] = ""
    if frame.empty:
        return pd.DataFrame(columns=FEATURE_COLUMNS)

    customer_cols = customers[["customer_id", "home_country", "home_city", "customer_segment", "risk_tier"]]
    device_cols = devices[["device_id", "first_seen_at", "trusted"]].rename(
        columns={"first_seen_at": "device_first_seen_at", "trusted": "device_trusted"}
    )
    merchant_cols = merchants[["merchant_id", "merchant_category_code", "merchant_category", "risk_tier"]].rename(
        columns={"risk_tier": "merchant_risk_tier"}
    )
    frame = frame.merge(customer_cols, on="customer_id", how="left")
    frame = frame.merge(device_cols, on="device_id", how="left")
    frame = frame.merge(merchant_cols, on="merchant_id", how="left")
    frame["device_first_seen_at"] = pd.to_datetime(frame["device_first_seen_at"], utc=True, errors="coerce")

    frame = frame.sort_values(["customer_id", "transaction_at", "transaction_id"]).reset_index(drop=True)
    frame["transaction_amount"] = frame["amount"]
    frame["transaction_hour"] = frame["transaction_at"].dt.hour
    frame["is_weekend"] = frame["transaction_at"].dt.dayofweek.isin([5, 6])
    frame["is_card_present"] = frame["channel"].eq("card_present")
    frame["is_international"] = frame["merchant_country"].ne(frame["home_country"])
    frame["is_new_device"] = (frame["transaction_at"] - frame["device_first_seen_at"]) <= pd.Timedelta(days=1)
    frame["is_new_merchant"] = frame.groupby(["customer_id", "merchant_id"]).cumcount().eq(0)
    frame["ip_country_mismatch"] = frame["is_international"] & frame["channel"].isin(["card_not_present", "mobile_wallet"])
    frame["device_age_days"] = (frame["transaction_at"] - frame["device_first_seen_at"]).dt.total_seconds().div(86400).clip(lower=0)

    frame["_customer_group"] = frame["customer_id"]
    frame = frame.groupby("_customer_group", group_keys=False).apply(_rolling_customer_features, include_groups=False)
    frame = frame.drop(columns=["_customer_group"], errors="ignore")
    frame["amount_to_customer_avg_ratio"] = frame["transaction_amount"] / frame["customer_avg_amount_30d"]
    frame.loc[~frame["amount_to_customer_avg_ratio"].replace([math.inf, -math.inf], pd.NA).notna(), "amount_to_customer_avg_ratio"] = pd.NA

    frame["_device_group"] = frame["device_id"]
    frame = frame.groupby("_device_group", group_keys=False).apply(_rolling_device_features, include_groups=False)
    frame = frame.drop(columns=["_device_group"], errors="ignore")
    frame["_merchant_group"] = frame["merchant_id"]
    frame = frame.groupby("_merchant_group", group_keys=False).apply(_rolling_merchant_features, include_groups=False)
    frame = frame.drop(columns=["_merchant_group"], errors="ignore")
    frame["_category_group"] = frame["merchant_category"]
    frame = frame.groupby("_category_group", group_keys=False).apply(_rolling_category_risk, include_groups=False)
    frame = frame.drop(columns=["_category_group"], errors="ignore")

    defaults = {
        "customer_avg_amount_7d": frame["transaction_amount"].median(),
        "customer_avg_amount_30d": frame["transaction_amount"].median(),
        "amount_to_customer_avg_ratio": 1.0,
        "transactions_last_10m": 0,
        "transactions_last_1h": 0,
        "amount_last_24h": 0.0,
        "unique_countries_last_7d": 0,
        "time_since_previous_transaction": -1,
        "distance_from_previous_transaction": 0.0,
        "failed_attempts_last_24h": 0,
        "device_age_days": 0.0,
        "customers_on_device_30d": 0,
        "cards_on_device_30d": 0,
        "device_transaction_velocity": 0,
        "device_fraud_rate_history": 0.0,
        "merchant_transaction_count_30d": 0,
        "merchant_fraud_rate_30d": 0.0,
        "merchant_chargeback_rate": 0.0,
        "merchant_category_risk": 0.0,
    }
    frame = frame.fillna(value=defaults)
    frame["feature_pipeline_run_id"] = pipeline_run_id

    return frame[FEATURE_COLUMNS].sort_values("transaction_at").reset_index(drop=True)
