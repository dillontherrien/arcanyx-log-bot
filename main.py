import os
import re
from datetime import datetime, timezone
from dotenv import load_dotenv
from interactions import Client, Intents, Member, SlashContext, listen, slash_command, slash_option, OptionType
from pymongo import MongoClient

# Loads environment variables
load_dotenv()

# Functions
def parse_amount(amount: str) -> int:
    """
    Takes the valid input and multiplies it based on the letter if present.
    """
    multipliers = {'k': 1_000, 'm': 1_000_000, 'b': 1_000_000_000}
    multiplier = amount[-1].lower()

    if multiplier in multipliers:
        return int(amount[:-1]) * multipliers[multiplier]
    
    return int(amount)

def get_mongo_client() -> MongoClient:
    """
    Creates a MongoDB client.
    """
    mongo_url = os.getenv("MONGO_URL")
    if not mongo_url:
        raise ValueError("MONGO_URL environment variable is not set.")
    
    client = MongoClient(mongo_url)
    return client

# Initializes the database
mongo_db = get_mongo_client()
# Selects the correct database
db = mongo_db["arcanyx"]

def insert_transaction(type: str, discord_id: str, staff_discord_id: str, amount: int):
    """
    Generic function to insert a transaction into the database.
    """
    # Ensure discord_id is a string or a primitive type
    if isinstance(discord_id, Member):
        discord_id = discord_id.id  # Extract the discordId from the Member object

    if isinstance(staff_discord_id, Member):
        staff_discord_id = staff_discord_id.id  # Extract the staff discordId from the Member object

    # Find the member_id based on discordId
    member = db.members.find_one({"discordId": str(discord_id)})
    staff = db.members.find_one({"discordId": str(staff_discord_id)})

    if not type:
        print(f"Transaction type not defined!")
        return
    if not member:
        print(f"Member with discordId {discord_id} not found!")
        return
    if not staff:
        print(f"Staff member with discordId {staff_discord_id} not found!")
        return

    # Create transaction document
    transaction = {
        "type": type,
        "member_id": member["_id"],
        "staff_id": staff["_id"],
        "amount": amount,
        "donation_time": datetime.now(timezone.utc)
    }

    # Insert into transaction_log
    result = db.transaction_log.insert_one(transaction)
    print(f"Transaction inserted with _id: {result.inserted_id}")

# Regex pattern to ensure OSRS gp logic is enforced
AMOUNT_PATTERN = r"^\d*[kmbKMB]?$"

# Common function for donation and payout
async def log_transaction(ctx: SlashContext, user: str, amount: str, transaction_type: str):
    await ctx.defer()
    amount_str = amount
    amount = amount.replace(",", "")
    
    # Checks that the input amount is valid format
    if not re.match(AMOUNT_PATTERN, amount):
        await ctx.send(f"Amount given ({amount}) is not valid. Please follow same logic in game for typing amounts (eg. 42244, 24m, 11k)")
        return

    amount = parse_amount(amount)
    staff = ctx.author_id

    insert_transaction(transaction_type, user, staff, amount)
    
    staff_member = await ctx.bot.fetch_user(staff)
    staff_mention = f"<@{staff_member.id}>"  # Mention staff

    # Send confirmation with staff mention at the end
    verb = "donated" if transaction_type == "donation" else "received"
    await ctx.send(f"{transaction_type.capitalize()} Logged! User `{user}` {verb} `{amount_str}` OSRS gold. Logged by {staff_mention}")

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
    description="Amount of OSRS gold. Same logic as in game",
    required=True,
    opt_type=OptionType.STRING
)
async def payout_command(ctx: SlashContext, user: str, amount: str):
    await log_transaction(ctx, user, amount, "payout")

# Creates bot object
bot = Client(intents=Intents.DEFAULT)

@listen()
async def on_ready():
    print("Ready")
    print(f"This bot is owned by {bot.owner}")

# Starts bot
bot.start(os.getenv("BOT_TOKEN"))
