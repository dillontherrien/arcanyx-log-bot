import logging
from constants import LOWER_LIMIT, UPPER_LIMIT

# Configure logging
logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s - %(levelname)s - %(message)s")

class Utils:
    def parse_amount(amount: str) -> int:
        """
        Takes the valid input and multiplies it based on the letter if present.
        """
        logging.info(f"Parsing amount: {amount}")
        multipliers = {'k': 1_000, 'm': 1_000_000, 'b': 1_000_000_000}
        multiplier = amount[-1].lower()

        if multiplier in multipliers:
            result = int(amount[:-1]) * multipliers[multiplier]
            logging.info(f"Multiplier used. Multiplied {amount} to {result:,}")
            return result

        result = int(amount)
        logging.info(f"Parsed amount from {amount} to {result:,}")
        return result
    
    def check_amount_limits(amount: int) -> bool:
        """
        Enforces lower limit of 1 and upper limit of 5 billion.
        Enforces OSRS gold logic (k, m, b accepted as multipliers)
        """
        logging.info(f"Checking if amount is inside transaction limits")

        # Amount lower limit check
        if amount < LOWER_LIMIT:
            logging.warning(
                f"{amount} is below transaction lower limit of {LOWER_LIMIT:,}.")
            return False
        # Amount upper limit check
        if amount > UPPER_LIMIT:
            logging.warning(
                f"{amount} exceeds transaction upper limit of {UPPER_LIMIT:,}.")
            return False

        return True