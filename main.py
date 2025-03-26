import os
import re
import logging
from datetime import datetime, timezone
from typing import Optional
from dotenv import load_dotenv
from interactions import Client, Intents, Member, SlashContext, listen, slash_command, slash_option, OptionType
from pymongo import MongoClient

# Configure logging
logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s - %(levelname)s - %(message)s")

# Constants
LOWER_LIMIT = 1
UPPER_LIMIT = 5_000_000_000
# Regex pattern to ensure OSRS gp logic is enforced
AMOUNT_PATTERN = r"^\d+[kmbKMB]?$"
NEGATIVE_TRANSACTIONS = ["payout"]  # Determines whether balance is added or removed

# Loads environment variables
load_dotenv()

# Error handlers


async def amount_invalid(ctx: SlashContext, amount: str):
    """
    Tells user that the given amount is invalid
    """
    await ctx.send(f"`{amount}` is not a valid amount. Please follow same logic in game for typing amounts (eg. 42244, 24m, 11k).", ephemeral=True)
    logging.warning(f"Invalid amount format: {amount}")


async def amount_outside_limits(ctx: SlashContext, amount: str):
    """
    Tells user that the given amount is outside of bounds
    """
    await ctx.send(f"`{amount}` is not valid amount. Amount must be between {LOWER_LIMIT:,} and {UPPER_LIMIT:,}.", ephemeral=True)
    logging.warning(f"Amount outside bounds: {amount}")


async def staff_not_found(ctx: SlashContext, user: OptionType.USER):
    """
    Tells user that the given amount is outside of bounds
    """

    await ctx.send(f"{user.mention} not found in the database. Is this actually a staff member?", ephemeral=True)

    logging.warning(f"Staff member not found database: {user}")


async def balance_not_found(ctx: SlashContext, user: OptionType.USER):
    """
    Tells user that the balance is not found for the given staff member
    """

    await ctx.send(f"{user.mention} does not have any balance.", ephemeral=True)

    logging.warning(f"Staff member has no balance: {user}")

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


def get_member_from_discord_id(discord_id: str) -> Optional[dict]:
    """
    Gets member from database, if none present, creates one 
    """
    if not discord_id:
        logging.warning("No discord id given to find user's object")
        return None

    member = db.members.find_one({"discordId": discord_id})

    if not member:
        logging.warning(f"No user found in data for discord id: {discord_id}")
        return None

    return member


def get_staff_member_from_discord_id(discord_id: str) -> Optional[dict]:
    """
    Gets staff from database, if none present, creates one 
    """
    if not discord_id:
        logging.warning("No discord id given to find staff's object")
        return None

    staff = db.members.find_one({"discordId": discord_id, "isStaff": True})

    if not staff:
        logging.warning(f"No staff found in database for discord id: {discord_id}")
        return None

    return staff


async def get_staff_balance(ctx: SlashContext, user: OptionType.USER) -> int:
    """
    Gets current balance of a staff member.

    """
    if not user:
        logging.warning("No user given to retreive balance")
        return

    logging.info(f"Getting balance for staff member {user}")

    staff = get_staff_member_from_discord_id(str(user.id))

    if not staff:
        await staff_not_found(ctx, user)
        return

    return int(staff.get("finances", {}).get("currentBalance", 0))


def set_staff_balance(user: OptionType.USER, amount: int):
    """
    Generic function to set a balance of a user in the database.
    """
    logging.info(f"Setting staff {user}'s balance to `{amount:,}`")

    if not user:
        logging.warning("No user given to set balance")
        return

    result = db.members.update_one(
        {"discordId": str(user.id)},
        {"$set": {"finances.currentBalance": amount}},
    )

    if result.matched_count > 0:
        logging.info(f"Updated balance to be {amount: ,}")
    else:
        logging.info(f"No updates were made, as there was no change")


def add_to_user_total(transaction_type: str, user: OptionType.USER, amount: int):
    """
    Adds to user's running total of donations or payouts
    """
    if transaction_type not in ["donation", "payout"]:
        logging.warning(f"Invalid transaction type given: {transaction_type}")
        return

    field = "totalDonations" if transaction_type == "donation" else "totalPayouts"
    logging.info(f"Setting staff {user}'s balance to `{amount:,}`")

    if not user:
        logging.warning("No user given to increase total")
        return

    update_field = "finances." + field
    result = db.members.update_one(
        {"discordId": str(user.id)},
        {"$set": {update_field: amount}},
    )

    if result.matched_count > 0:
        logging.info(f"Updated {transaction_type} total to be {amount: ,}")
    else:
        logging.info(f"No updates were made, as there was no change")


async def insert_transaction(ctx: SlashContext, transaction_type: str, user: OptionType.USER, staff: OptionType.USER, amount: int):
    """
    Generic function to insert a transaction into the database.
    """
    logging.info(
        f"Inserting transaction: type={transaction_type}, user={user}, staff={staff}, amount={amount}")

    member = get_member_from_discord_id(str(user.id))
    staff = get_member_from_discord_id(str(staff.id))

    if not transaction_type:
        logging.error("Transaction type not defined!")
        return
    if not member:
        logging.warning(f"Member with discord ID {user.id} not found!")
        return
    if not staff:
        await staff_not_found(ctx, staff)
        return

    transaction = {
        "type": transaction_type,
        "member_id": member["_id"],
        "staff_id": staff["_id"],
        "amount": amount,
        "donation_time": datetime.now(timezone.utc)
    }

    result = db.transaction_log.insert_one(transaction)
    logging.info(f"Transaction inserted with _id: {result.inserted_id}")

    add_to_user_total(transaction_type, user, amount)


# TODO: Log transfer function
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
async def log_transaction(ctx: SlashContext, user: OptionType.USER, amount: str, transaction_type: str):
    logging.info(
        f"Logging transaction: type={transaction_type}, user={user}, amount={amount}")
    await ctx.defer()
    amount_str: str = amount
    amount = amount.replace(",", "")

    if not re.match(AMOUNT_PATTERN, amount):
        await amount_invalid(ctx, amount_str)
        return

    amount: int = parse_amount(amount)

    if not check_amount_limits(amount):
        await amount_outside_limits(ctx, amount_str)
        return

    staff = get_staff_member_from_discord_id(str(ctx.author.id))
    
    if not staff:
        await staff_not_found(ctx, ctx.author)
        logging.warning(f"Command executor not staff member, cannot complete transaction!")
        return

    balance = await get_staff_balance(ctx, ctx.author) or 0

    adj_balance_amount = amount

    # Payouts must exist in the balance
    if transaction_type in NEGATIVE_TRANSACTIONS:
        # Ensures staff member has the funds to payout to user
        if balance < amount:
            await ctx.send(f"You do not have the balance for this {transaction_type}. Current balance is `{balance:,}`, Requested amount is `{amount:,}`")
            return

        adj_balance_amount *= -1

    balance += adj_balance_amount  # New balance
    set_staff_balance(ctx.author, balance)
    logging.info(f"{ctx.author.mention}'s new balance is {balance:,}")

    await insert_transaction(ctx, transaction_type, user, ctx.author, amount)

    verb = "donated" if transaction_type == "donation" else "received"

    await ctx.send(f"{transaction_type.capitalize()} Logged! User {user.mention} {verb} `{amount:,}` OSRS gold. Your new balance is `{balance:,}`", ephemeral=True)
    logging.info(
        f"Transaction successfully logged: {transaction_type} for {user}")


# Command that gets the balance for a staff member
@slash_command(name="balance", description="Gets balance for a given staff member")
@slash_option(
    name="user",
    description="Staff member",
    required=False,
    opt_type=OptionType.USER
)
async def get_balance_command(ctx: SlashContext, user: OptionType.USER = None):
    await ctx.defer()
    if user is None:
        user = ctx.author

    balance = await get_staff_balance(ctx, user)

    if balance is not None:
        await ctx.send(f"{user.mention}'s current balance is `{balance:,}`", ephemeral=True)


# Command that sets a staff member's balance
@slash_command(name="setbalance", description="Set a staff member's balance")
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
async def set_balance_command(ctx: SlashContext, user: OptionType.USER, amount: str):
    await ctx.defer()
    amount_str: str = amount
    amount = amount.replace(",", "")

    if not re.match(AMOUNT_PATTERN, amount):
        await amount_invalid(ctx, amount_str)
        return

    amount = parse_amount(amount)

    if not check_amount_limits(amount):
        await amount_outside_limits(ctx, amount_str)
        return

    set_staff_balance(user, amount)
    await ctx.send(f"{user.mention}'s balance has been set to `{amount:,}`", ephemeral=True)


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
async def donation_command(ctx: SlashContext, user: OptionType.USER, amount: str):
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
async def payout_command(ctx: SlashContext, user: OptionType.USER, amount: str):
    await log_transaction(ctx, user, amount, "payout")

# Creates bot object
bot = Client(intents=Intents.DEFAULT)


@listen()
async def on_ready():
    logging.info("Bot is ready")
    logging.info(f"This bot is owned by {bot.owner}")

    # Define the channel ID where the bot should post the startup message
    CHANNEL_ID = int(os.getenv("BOT_COMMANDS_CHANNEL_ID"))

    # Fetch the channel object
    channel = await bot.fetch_channel(CHANNEL_ID)
    if channel:
        # Construct the command list message
        commands = [
            ("/balance", "Gets the balance for a given staff member."),
            ("/setbalance", "Set a staff member's balance."),
            ("/donation", "Log a donation."),
            ("/payout", "Log a payout."),
        ]

        command_list = "\n".join(
            f"**{cmd}** - {desc}" for cmd, desc in commands)
        startup_message = f"**Bot is online!**\nHere are the available commands:\n{command_list}"

        # Send the message
        # await channel.send(startup_message)
    else:
        logging.warning("Could not find the startup message channel.")


# Starts bot
if __name__ == "__main__":
    logging.info("Starting bot...")
    bot.start(os.getenv("BOT_TOKEN"))
