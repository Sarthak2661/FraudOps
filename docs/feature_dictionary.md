# FraudOps Feature Dictionary

All rolling features are point-in-time safe: they use only transactions with `transaction_at` earlier than the scored transaction.

| Feature | Business meaning | Formula | Source fields | Window | Null handling | Leakage risk | Expected range |
|---|---|---|---|---|---|---|---|
| transaction_amount | Purchase size being scored | `amount` | transaction.amount | Current transaction | Required by validation | Low | > 0 |
| transaction_hour | Hour-of-day behavior | Hour from `transaction_at` | transaction.transaction_at | Current transaction | Required by validation | Low | 0-23 |
| is_weekend | Weekend spending flag | Day of week in Saturday/Sunday | transaction.transaction_at | Current transaction | Required by validation | Low | true/false |
| is_card_present | Physical card transaction flag | `channel == card_present` | transaction.channel | Current transaction | False if channel differs | Low | true/false |
| is_international | Merchant country differs from customer home country | `merchant_country != home_country` | transaction.merchant_country, customer.home_country | Current transaction | False only if both known; validation protects keys | Low | true/false |
| is_new_device | Device first seen near transaction time | `transaction_at - device_first_seen_at <= 1 day` | transaction.transaction_at, device.first_seen_at | Current/prior device metadata | Missing device age becomes 0 after validation | Medium if device metadata is backfilled incorrectly | true/false |
| is_new_merchant | Customer has no prior transaction with this merchant | Prior count for customer and merchant equals 0 | transaction.customer_id, merchant_id, transaction_at | All prior history | First occurrence is true | Low | true/false |
| ip_country_mismatch | Online/mobile international mismatch proxy | `is_international and channel in card_not_present/mobile_wallet` | channel, merchant_country, customer.home_country | Current transaction | False when not online/mobile | Low | true/false |
| customer_avg_amount_7d | Recent customer spending baseline | Mean prior amount for customer | customer_id, amount, transaction_at | Prior 7 days | Filled with global median for first history | Low | >= 0 |
| customer_avg_amount_30d | Longer customer spending baseline | Mean prior amount for customer | customer_id, amount, transaction_at | Prior 30 days | Filled with global median for first history | Low | >= 0 |
| amount_to_customer_avg_ratio | Size relative to customer baseline | `transaction_amount / customer_avg_amount_30d` | amount, customer_avg_amount_30d | Prior 30 days | Filled with 1.0 when no baseline | Low | >= 0 |
| transactions_last_10m | Short burst velocity | Count prior customer transactions | customer_id, transaction_at | Prior 10 minutes | Filled with 0 | Low | >= 0 |
| transactions_last_1h | Hourly customer velocity | Count prior customer transactions | customer_id, transaction_at | Prior 1 hour | Filled with 0 | Low | >= 0 |
| amount_last_24h | Recent customer spend | Sum prior customer amounts | customer_id, amount, transaction_at | Prior 24 hours | Filled with 0 | Low | >= 0 |
| unique_countries_last_7d | Recent geographic spread | Distinct prior merchant countries | customer_id, merchant_country, transaction_at | Prior 7 days | Filled with 0 | Low | >= 0 |
| time_since_previous_transaction | Customer recency | Minutes since previous customer transaction | customer_id, transaction_at | Immediate prior transaction | `-1` when no prior transaction | Low | -1 or >= 0 |
| distance_from_previous_transaction | Geographic jump proxy | Haversine distance between prior and current merchant countries | merchant_country, transaction_at | Immediate prior transaction | 0 when unknown/no prior | Medium; country-level approximation | >= 0 km |
| failed_attempts_last_24h | Recent declined activity | Count prior declined customer transactions | customer_id, status, transaction_at | Prior 24 hours | Filled with 0 | Low | >= 0 |
| device_age_days | Age of device at transaction | `transaction_at - device_first_seen_at` in days | device.first_seen_at, transaction_at | Current/prior device metadata | Filled with 0 | Medium if device first-seen is corrected later | >= 0 |
| customers_on_device_30d | Device sharing risk | Distinct prior customers on device | device_id, customer_id, transaction_at | Prior 30 days | Filled with 0 | Low | >= 0 |
| cards_on_device_30d | Device/card sharing risk | Distinct prior cards on device | device_id, card_id, transaction_at | Prior 30 days | Filled with 0 | Low | >= 0 |
| device_transaction_velocity | Device burst velocity | Count prior device transactions | device_id, transaction_at | Prior 1 hour | Filled with 0 | Low | >= 0 |
| device_fraud_rate_history | Prior known fraud on device | Expanding prior fraud-label mean | device_id, fraud_label, transaction_at | All prior device history | Filled with 0 | Medium; only use labels available at scoring time in production | 0-1 |
| merchant_transaction_count_30d | Merchant activity volume | Count prior merchant transactions | merchant_id, transaction_at | Prior 30 days | Filled with 0 | Low | >= 0 |
| merchant_fraud_rate_30d | Recent merchant fraud risk | Mean prior fraud labels for merchant | merchant_id, fraud_label, transaction_at | Prior 30 days | Filled with 0 | Medium; production should respect label availability | 0-1 |
| merchant_chargeback_rate | Historical merchant chargeback risk | Expanding prior chargeback-source mean | merchant_id, label_source, transaction_at | All prior merchant history | Filled with 0 | Medium; chargebacks arrive late | 0-1 |
| merchant_category_risk | Category-level fraud baseline | Expanding prior fraud-label mean by merchant category | merchant_category, fraud_label, transaction_at | All prior category history | Filled with 0 | Medium; production should respect label availability | 0-1 |

## Target Columns Kept With Features

| Column | Purpose |
|---|---|
| transaction_id | Join key back to source transaction |
| transaction_external_id | Human-readable transaction identifier |
| customer_id | Customer-level grouping and join key |
| account_id | Account-level join key |
| card_id | Card-level join key |
| device_id | Device-level join key |
| merchant_id | Merchant-level join key |
| transaction_at | Point-in-time feature timestamp |
| fraud_label | Current label for exploration/training; production scoring should not use this as a feature |
| fraud_scenario | Synthetic scenario explanation for lineage and QA |
| feature_pipeline_run_id | Pipeline lineage for curated features |

## Leakage Notes

- Rolling windows use `closed="left"`, excluding the current transaction.
- Fraud-rate features are suitable for offline exploration. In a production feature store, they should use only labels where `label_available_at <= transaction_at`.
- `fraud_label`, `label_source`, `chargeback_date`, and analyst outcome fields must never be model input features for real-time scoring.
