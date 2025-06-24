LOWER_LIMIT = 0
UPPER_LIMIT = 5_000_000_000
GAP_AMOUNT = 15
# Regex pattern to ensure OSRS gp logic is enforced
AMOUNT_PATTERN = r"^\d+[kmbKMB]?$"
ALL_TRANSACTIONS = ["donation", "payout", "event", "buy in"]
# Determines whether balance is added or removed
NEGATIVE_TRANSACTIONS = ["payout"]