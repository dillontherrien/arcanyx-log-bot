import os
import re
import logging
from datetime import datetime, timezone
from dotenv import load_dotenv
from interactions import Client, Intents, Member, SlashContext, listen, slash_command, slash_option, OptionType
from pymongo import MongoClient

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Constants
LOWER_LIMIT = 1
UPPER_LIMIT = 5_000_000_000
AMOUNT_PATTERN = r"^\d+[kmbKMB]?$" # Regex pattern to ensure OSRS gp logic is enforced

# Loads environment variables
load_dotenv()

# Error handlers
async def amount_invalid(ctx: SlashContext, amount: str):
    """
    Tells user that the given amount is invalid
    """
    await ctx.send(f"`{amount}` is not a valid amount. Please follow same logic in game for typing amounts (eg. 42244, 24m, 11k).")
    raise ValueError(f"Invalid amount format: {amount}")

async def amount_outside_limits(ctx: SlashContext, amount: str):
    """
    Tells user that the given amount is outside of bounds
    """
    await ctx.send(f"`{amount}` is not valid amount. Amount must be between {LOWER_LIMIT:,} and {UPPER_LIMIT:,}.")
    raise ValueError(f"Amount outside bounds: {amount}")
    

async def staff_not_found(ctx: SlashContext, discord_id: str):
    """
    Tells user that the given amount is outside of bounds
    """
    await ctx.send(f"Staff member with discord_id `{discord_id}` not found in the database.")
    raise ValueError(f"Staff member not found database: {discord_id}")

# Functions
def parse_amount(amount: str) -> int:
    """
    Takes the valid input and multiplies it based on the letter if present.
    """
    logging.info(f"Parsing amount: {amount}")
    multipliers = {'k': 1_000, 'm': 1_000_000, 'b': 1_000_000_000}
    multiplier = amount[-1].lower()

    if multiplier in multipliers:
        result = int(amount[:-1]) * multipliers[multiplier]
        logging.info(f"Converted {amount} to {result}")
        return result
    
    result = int(amount)
    logging.info(f"Converted {amount} to {result}")
    return result

def check_amount_limits(amount: int) -> bool:
    """
    Enforces lower limit of 1 and upper limit of 5 billion.
    Enforces OSRS gold logic (k, m, b accepted as multipliers)
    """
    logging.info(f"Checking if amount is inside transaction limits")
    
    # Amount lower limit check
    if amount < LOWER_LIMIT:
        logging.warning(f"{amount} is below transaction lower limit of {LOWER_LIMIT:,}.")
        return False
    # Amount upper limit check
    if amount > UPPER_LIMIT:
        logging.warning(f"{amount} exceeds transaction upper limit of {UPPER_LIMIT:,}.")
        return False
    
    return True

def get_mongo_client() -> MongoClient:
    """
    Creates a MongoDB client.
    """
    mongo_url = os.getenv("MONGO_URL")
    if not mongo_url:
        logging.error("MONGO_URL environment variable is not set.")
        raise ValueError("MONGO_URL environment variable is not set.")
    
    logging.info("Connecting to MongoDB...")
    client = MongoClient(mongo_url)
    return client

# Initializes the database
mongo_db = get_mongo_client()
# Selects the correct database
db = mongo_db["arcanyx"]

# TODO: Balance mongodb collection structure
# TODO: Get balance function
def get_staff_balance(ctx: SlashContext, staff_discord_id: str):
    """
    Gets current balance of a staff member.
    """
    if not staff_discord_id:
        logging.warning("No staff discord id given to retreive balance")
        return
    
    logging.info(f"Getting balance for staff member {staff_discord_id}")
    
    staff = db.members.find_one({"discordId": str(staff_discord_id)})
    
    if not staff:
        staff_not_found(ctx, staff_discord_id)
        return

    # Retreives balance from MongoDB
    # balance = db.balances.find_one


def insert_transaction(ctx: SlashContext, type: str, discord_id: str, staff_discord_id: str, amount: int):
    """
    Generic function to insert a transaction into the database.
    """
    logging.info(f"Inserting transaction: type={type}, user={discord_id}, staff={staff_discord_id}, amount={amount}")

    if isinstance(discord_id, Member):
        discord_id = discord_id.id  # Extract the discordId from the Member object
    if isinstance(staff_discord_id, Member):
        staff_discord_id = staff_discord_id.id  # Extract the staff discordId from the Member object

    member = db.members.find_one({"discordId": str(discord_id)})
    staff = db.members.find_one({"discordId": str(staff_discord_id)})

    if not type:
        logging.error("Transaction type not defined!")
        return
    if not member:
        logging.warning(f"Member with discordId {discord_id} not found!")
        return
    if not staff:
        staff_not_found(ctx, staff_discord_id)

    transaction = {
        "type": type,
        "member_id": member["_id"],
        "staff_id": staff["_id"],
        "amount": amount,
        "donation_time": datetime.now(timezone.utc)
    }

    result = db.transaction_log.insert_one(transaction)
    logging.info(f"Transaction inserted with _id: {result.inserted_id}")


#TODO: Log transfer function
# async def log_transfer(ctx: SlashContext, user_from: str, user_to: str, amount: str):
#     logging.info(f"Logging transfer: from_user={user_from}, to_user={user_to}, amount={amount}")
#     await ctx.defer()
#     amount_str : str = amount
#     amount = amount.replace(",", "")

#     if not re.match(AMOUNT_PATTERN, amount):
#         amount_invalid(ctx, amount_str)
#         return
    
#     amount = parse_amount(amount)
    
#     if not check_amount_limits(amount):
#         amount_outside_limits(ctx, amount_str)
#         return
    

# Common function for donation and payout
async def log_transaction(ctx: SlashContext, user: str, amount: str, transaction_type: str):
    logging.info(f"Logging transaction: type={transaction_type}, user={user}, amount={amount}")
    await ctx.defer()
    amount_str : str = amount
    amount = amount.replace(",", "")
    
    if not re.match(AMOUNT_PATTERN, amount):
        amount_invalid(ctx, amount_str)

    amount = parse_amount(amount)
    
    if not check_amount_limits(amount):
        amount_outside_limits(ctx, amount_str)
    
    staff = ctx.author_id

    insert_transaction(ctx, transaction_type, user, staff, amount)
    
    staff_member = await ctx.bot.fetch_user(staff)
    staff_mention = f"<@{staff_member.id}>"
    
    verb = "donated" if transaction_type == "donation" else "received"
    await ctx.send(f"{transaction_type.capitalize()} Logged! User `{user}` {verb} `{amount_str}` OSRS gold. Logged by {staff_mention}")
    logging.info(f"Transaction successfully logged: {transaction_type} for {user}")

# Command that logs player donations
@slash_command(name="donation", description="Log a donation")
@slash_option(      
    name="user",
    description="User this transaction is for",
    required=True,
    opt_type=OptionType.USER
)
@slash_option(
    name="amount",
    description="Amount of OSRS gold. Same logic as in game",
    required=True,
    opt_type=OptionType.STRING
)
async def donation_command(ctx: SlashContext, user: str, amount: str):
    await log_transaction(ctx, user, amount, "donation")

# Command that logs player payouts
@slash_command(name="payout", description="Log a payout")
@slash_option(      
    name="user",
    description="User this transaction is for",
    required=True,
    opt_type=OptionType.USER
)
@slash_option(
    name="amount",
    description="Amount of OSRS gold. Same logic as in game (Between 1 and 5 billion)",
    required=True,
    opt_type=OptionType.STRING
)
async def payout_command(ctx: SlashContext, user: str, amount: str):
    await log_transaction(ctx, user, amount, "payout")

# Creates bot object
bot = Client(intents=Intents.DEFAULT)

@listen()
async def on_ready():
    logging.info("Bot is ready")
    logging.info(f"This bot is owned by {bot.owner}")

# Starts bot
if __name__ == "__main__":
    logging.info("Starting bot...")
    bot.start(os.getenv("BOT_TOKEN"))
