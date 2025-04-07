LOWER_LIMIT = 1
UPPER_LIMIT = 5_000_000_000
# Regex pattern to ensure OSRS gp logic is enforced
AMOUNT_PATTERN = r"^\d+[kmbKMB]?$"
# Determines whether balance is added or removed
NEGATIVE_TRANSACTIONS = ["payout"]