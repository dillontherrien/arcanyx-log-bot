from datetime import datetime
import os
import re
import logging
import asyncio
from datetime import datetime, timezone
from typing import Optional
from dotenv import load_dotenv
from interactions import Client, Intents, SlashCommandChoice, SlashContext, listen, slash_command, slash_option, OptionType, Member
from interactions.api.events import MemberAdd
from pymongo import MongoClient
from constants import LOWER_LIMIT, UPPER_LIMIT, AMOUNT_PATTERN, ALL_TRANSACTIONS, NEGATIVE_TRANSACTIONS, GAP_AMOUNT
from utils import Utils


# Configure logging
logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s - %(levelname)s - %(message)s")

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

    await ctx.send(f"<@!{user.id}> not found in the database. Is this actually a staff member?", ephemeral=True)

    logging.warning(f"Staff member not found database: {user}")


async def balance_not_found(ctx: SlashContext, user: OptionType.USER):
    """
    Tells user that the balance is not found for the given staff member
    """

    await ctx.send(f"<@!{user.get('discordId')}> does not have any balance.", ephemeral=True)

    logging.warning(f"Staff member has no balance: {user}")

# Functions


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


def get_top_donations():
    """
    Gets the top donations and formats them with the top donor highlighted
    """
    results = db.members.find(
        {"finances.totalDonations": {"$gte": 1_000_000}},
        {
            "discordId": 1,
            "discordUsername": 1,
            "finances.totalDonations": 1
        }
    ).sort(
        [("finances.totalDonations", -1)]
    ).limit(100)

    results = list(results)  # Convert cursor to list

    if not results:
        return "No donations found."

    categories = {
        "<@&1263860564849987604> (1b+ Donor)": [],
        "<@&1218903586222899270> (500m+ Donor)": [],
        "<@&1268916957374189599> (250m+ Donor)": [],
        "<@&1268919266380353577> (100m+ Donor)": [],
        "50m+ Donor": [],
        "25m+ Donor": [],
        "10m+ Donor": [],
        "0-9m Donor": []
    }

    for transaction in results:
        amount = transaction["finances"]["totalDonations"]
        discord_id = transaction["discordId"]

        if amount >= 1_000_000_000:
            categories["<@&1263860564849987604> (1b+ Donor)"].append(
                f"<@!{discord_id}> - {int(amount / 1_000_000):,}m")
        elif amount >= 500_000_000:
            categories["<@&1218903586222899270> (500m+ Donor)"].append(
                f"<@!{discord_id}> - {int(amount / 1_000_000):,}m")
        elif amount >= 250_000_000:
            categories["<@&1268916957374189599> (250m+ Donor)"].append(
                f"<@!{discord_id}> - {int(amount / 1_000_000):,}m")
        elif amount >= 100_000_000:
            categories["<@&1268919266380353577> (100m+ Donor)"].append(
                f"<@!{discord_id}> - {int(amount / 1_000_000):,}m")
        elif amount >= 50_000_000:
            categories["50m+ Donor"].append(
                f"<@!{discord_id}> - {int(amount / 1_000_000):,}m")
        elif amount >= 25_000_000:
            categories["25m+ Donor"].append(
                f"<@!{discord_id}> - {int(amount / 1_000_000):,}m")
        elif amount >= 10_000_000:
            categories["10m+ Donor"].append(
                f"<@!{discord_id}> - {int(amount / 1_000_000):,}m")
        else:
            categories["0-9m Donor"].append(
                f"<@!{discord_id}> - {int(amount / 1_000_000):,}m")

    formatted_message = "__Donation Leaderboard__\n"
    for category, members in categories.items():
        if members:
            formatted_message += f"**{category}** \n" + \
                "\n".join(members) + "\n\n"

    # Add timestamp at the end
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    formatted_message += f"_Updated as of {current_time}_"

    return formatted_message.rstrip("\n")


def get_total_balance() -> str:
    """
    Gets the total balance of each staff member and creates a string message displaying the information
    """
    staff_members = db.members.find({"isStaff": True, "finances.currentBalance": {
        "$gt": 0}}).sort({"finances.currentBalance": -1}).to_list()
    logging.info(staff_members)
    total_balance = f"TOTAL CLAN BALANCE: **{sum(staff["finances"]["currentBalance"] for staff in staff_members):,}gp**\n\n"

    member_totals = "__**BALANCE BY USER**__\n"
    member_totals += "\n".join(
        f"<@!{staff.get('discordId')}> - {staff["finances"]["currentBalance"]:,}gp" for staff in staff_members)

    return total_balance + member_totals


def get_recent_transactions() -> str:
    TRANSACTION_LIMIT = 15

    results = db.transaction_log.aggregate([
        {
            "$lookup": {
                "from": "members",
                "localField": "member_id",
                "foreignField": "_id",
                "as": "member_info"
            }
        },
        {
            "$unwind": {
                "path": "$member_info",
                "preserveNullAndEmptyArrays": True
            }
        },
        {
            "$lookup": {
                "from": "members",
                "localField": "staff_id",
                "foreignField": "_id",
                "as": "staff_info"
            }
        },
        {
            "$unwind": {
                "path": "$staff_info",
                "preserveNullAndEmptyArrays": True
            }
        },
        {
            "$match": {
                "type": {
                    "$not": {
                        "$regex": "event",
                        "$options": "i"  # case-insensitive
                    }
                }
            }
        },
        {
            "$project": {
                "_id": 0,
                "discordUsername": "$member_info.discordUsername",
                "staff_discordUsername": "$staff_info.discordUsername",
                "type": 1,
                "amount": 1,
                "donation_time": 1,
                "reason": 1
            }
        },
        {
            "$sort": {
                "donation_time": -1
            }
        },
        {
            "$limit": TRANSACTION_LIMIT
        }
    ])

    transaction_list = f"\n__**LAST {TRANSACTION_LIMIT} TRANSACTIONS**__\n```diff\n"
    transaction_list += "  Amount   Type        Who            Staff          When (UTC)     Reason\n"

    def pad_str(input_str: str, custom_pad: int = None) -> str:
        global GAP_AMOUNT
        if custom_pad is None:
            custom_pad = GAP_AMOUNT
        if input_str is None:
            input_str = ""
        return input_str[:custom_pad - 1].ljust(custom_pad)

    for transaction in results:
        prefix = "-" if transaction["type"] in NEGATIVE_TRANSACTIONS else "+"

        raw_amount = transaction["amount"]
        if raw_amount >= 1_000_000:
            display_amount = f"{int(raw_amount / 1_000_000)}m"
        else:
            display_amount = f"{int(raw_amount / 1_000)}k"

        amount = pad_str(display_amount, GAP_AMOUNT - 6)
        transaction_type = pad_str(
            transaction["type"].capitalize(), GAP_AMOUNT - 3)
        who = pad_str(transaction["discordUsername"])
        staff = pad_str(transaction["staff_discordUsername"])

        # Format donation_time
        dt = transaction.get("donation_time")
        if isinstance(dt, str):
            dt = datetime.fromisoformat(dt)
        if isinstance(dt, datetime):
            # e.g., 6/19 20:14 (on Linux/macOS)
            when = dt.strftime("%-m/%-d %H:%M")
        else:
            when = "?"

        when = pad_str(when)
        reason = transaction.get(
            "reason") if transaction["type"] in NEGATIVE_TRANSACTIONS else " " * (GAP_AMOUNT + 10)
        new_line = f"{prefix} {amount}{transaction_type}{who}{staff}{when}{reason}"

        transaction_list += new_line + "\n"

    transaction_list += "\n```"
    transaction_list += "\n\n"
    transaction_list += get_total_balance()

    # Add relative current time in Discord format:
    now = datetime.now(timezone.utc)
    unix_ts = int(now.timestamp())
    transaction_list += f"\n\nLast updated: <t:{unix_ts}:R>"
    return transaction_list


def get_recent_events() -> str:
    TRANSACTION_LIMIT = 15

    results = db.transaction_log.aggregate([
        {
            "$lookup": {
                "from": "members",
                "localField": "member_id",
                "foreignField": "_id",
                "as": "member_info"
            }
        },
        {
            "$unwind": {
                "path": "$member_info",
                "preserveNullAndEmptyArrays": True
            }
        },
        {
            "$lookup": {
                "from": "members",
                "localField": "staff_id",
                "foreignField": "_id",
                "as": "staff_info"
            }
        },
        {
            "$unwind": {
                "path": "$staff_info",
                "preserveNullAndEmptyArrays": True
            }
        },
        {
            "$match": {
                "type": {
                    "$regex": "event",
                    "$options": "i"
                }
            }
        },
        {
            "$project": {
                "_id": 0,
                "discordUsername": "$member_info.discordUsername",
                "staff_discordUsername": "$staff_info.discordUsername",
                "type": 1,
                "amount": 1,
                "donation_time": 1,
                "reason": 1
            }
        },
        {
            "$sort": {
                "donation_time": -1
            }
        },
        {
            "$limit": TRANSACTION_LIMIT
        }
    ])

    transaction_list = f"\n__**LAST {TRANSACTION_LIMIT} EVENTS**__\n```fix\n"
    transaction_list += "Amount   Who            Staff          When (UTC)     Reason\n"

    def pad_str(input_str: str, custom_pad: int = None) -> str:
        global GAP_AMOUNT
        if custom_pad is None:
            custom_pad = GAP_AMOUNT
        if input_str is None:
            input_str = ""
        return input_str[:custom_pad - 1].ljust(custom_pad)

    for transaction in results:

        raw_amount = transaction["amount"]
        if raw_amount >= 1_000_000:
            display_amount = f"{int(raw_amount / 1_000_000)}m"
        else:
            display_amount = f"{int(raw_amount / 1_000)}k"

        amount = pad_str(display_amount, GAP_AMOUNT - 6)
        who = pad_str(transaction["discordUsername"])
        staff = pad_str(transaction["staff_discordUsername"])

        # Format donation_time
        dt = transaction.get("donation_time")
        if isinstance(dt, str):
            dt = datetime.fromisoformat(dt)
        if isinstance(dt, datetime):
            # e.g., 6/19 20:14 (on Linux/macOS)
            when = dt.strftime("%-m/%-d %H:%M")
        else:
            when = "?"

        when = pad_str(when)
        reason = transaction.get("reason")
        new_line = f"{amount}{who}{staff}{when}{reason}"

        transaction_list += new_line + "\n"

    transaction_list += "\n```"

    # Add relative current time in Discord format:
    now = datetime.now(timezone.utc)
    unix_ts = int(now.timestamp())
    transaction_list += f"\n\nLast updated: <t:{unix_ts}:R>"
    return transaction_list


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


async def get_staff_member_from_discord_id(discord_id: str) -> Optional[dict]:
    """
    Gets staff from database, if none present, creates one 
    """
    if not discord_id:
        logging.warning("No discord id given to find staff's object")
        return None

    logging.info(f"Looking for staff member with discord id : {discord_id}")
    staff = db.members.find_one({"discordId": discord_id, "isStaff": True})

    if not staff:
        logging.warning(
            f"No staff found in database for discord id: {discord_id}")
        return None
    logging.info(f"Staff member found: {staff}")
    return staff


def set_staff_balance(user: OptionType.USER, amount: int):
    """
    Generic function to set a balance of a user in the database.
    """
    logging.info(f"Setting staff {user}'s balance to {amount:,}")

    if not user:
        logging.warning("No user given to set balance")
        return

    result = db.members.update_one(
        {"discordId": str(user.get('discordId'))},
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
    if transaction_type not in ALL_TRANSACTIONS:
        logging.warning(f"Invalid transaction type given: {transaction_type}")
        return

    logging.info(f"Adding **{amount:,}** to user's {transaction_type} total.")

    if not user:
        logging.warning(
            f"No user given to increase {transaction_type} total by **{amount:,}**.")
        return

    field = "totalDonations" if transaction_type in [
        "donation", "event"] else "totalPayouts"
    update_field = "finances." + field
    result = db.members.update_one(
        {"discordId": str(user.id)},
        {"$inc": {update_field: amount}},
    )

    if result.matched_count > 0:
        logging.info(f"Updated {field} total to be {amount: ,}")
    else:
        logging.info(
            f"No updates were made, as there was no member document found.")


async def insert_transaction(ctx: SlashContext, transaction_type: str, user: OptionType.USER, staff: OptionType.USER, amount: int, reason: str = None):
    """
    Generic function to insert a transaction into the database.
    """
    logging.info(
        f"Inserting transaction: type={transaction_type}, user={user}, staff={staff}, amount={amount}")

    member = get_member_from_discord_id(str(user.id))

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
    # Add reason if one is given
    if reason:
        transaction["reason"] = reason

    result = db.transaction_log.insert_one(transaction)
    logging.info(f"Transaction inserted with _id: {result.inserted_id}")

    add_to_user_total(transaction_type, user, amount)

    asyncio.create_task(update_top_donations(ctx))
    asyncio.create_task(update_recent_transactions(ctx))
    asyncio.create_task(update_recent_events(ctx))


# TODO: Log transfer function
async def log_transfer(ctx: SlashContext, staff_from_user: OptionType.USER, staff_to_user: OptionType.USER, amount: str):
    logging.info(
        f"Logging transfer: from_user={staff_from_user}, to_user={staff_from_user}, amount={amount}")
    amount_str: str = amount
    amount = amount.replace(",", "")

    if not re.match(AMOUNT_PATTERN, amount):
        await amount_invalid(ctx, amount_str)
        return

    amount: int = Utils.parse_amount(amount)

    if not Utils.check_amount_limits(amount):
        await amount_outside_limits(ctx, amount_str)
        return

    if staff_from_user == staff_to_user:
        logging.warning(
            "'From' staff member is same as 'To' staff member.")
        await ctx.send(f"You cannot transfer from and to the same staff member!")
        return

    staff_from = await get_staff_member_from_discord_id(str(staff_from_user.id))

    if not staff_from:
        await staff_not_found(ctx, staff_from_user)
        logging.warning(
            "'From' staff member not found. Cannot complete transaction.")
        return

    staff_to = await get_staff_member_from_discord_id(str(staff_to_user.id))

    if not staff_to:
        await staff_not_found(ctx, staff_to_user)
        logging.warning(
            "'From' staff member not found. Cannot complete transaction.")
        return

    logging.info(
        f"Trying to get balance from {staff_from}. Their finances {staff_from.get("finances")}.")
    staff_from_balance = staff_from.get("finances")["currentBalance"] or 0

    if staff_from_balance < amount:
        await ctx.send(f"<@!{staff_from.get('discordId')}> does not have the balance for this transfer. Current balance is **{staff_from_balance:,}**, Requested amount is **{amount:,}**")
        return

    logging.info(
        f"Trying to get balance from {staff_to}. Their finances {staff_to.get("finances")}.")
    staff_to_balance = staff_to.get("finances")["currentBalance"] or 0

    staff_from_balance -= amount
    set_staff_balance(staff_from, staff_from_balance)
    logging.info(f"{staff_from}'s new balance is {staff_from_balance:,}")

    staff_to_balance += amount
    set_staff_balance(staff_to, staff_to_balance)
    logging.info(f"{staff_to}'s new balance is {staff_to_balance:,}")

    transfer = {
        "from_id": staff_from["_id"],
        "to_id": staff_to["_id"],
        "amount": amount,
        "transfer_time": datetime.now(timezone.utc)
    }

    result = db.transfer_log.insert_one(transfer)
    logging.info(f"Transfer inserted with _id: {result.inserted_id}")

    await ctx.send(f"Transfer successful! **{amount:,}gp** transferred from <@!{staff_from.get('discordId')}> to <@!{staff_to.get('discordId')}>.", ephemeral=True)

    logging.info(
        f"Transfer successful! **{amount:,}gp** transferred from <@!{staff_from.get('discordId')}> to <@!{staff_to.get('discordId')}>.")

    asyncio.create_task(update_recent_transactions(ctx))


async def log_event(ctx: SlashContext, staff: OptionType.USER, user: OptionType.USER, amount: str, reason: str = None):
    logging.info(f"Logging event: user={user}, amount={amount}")
    await ctx.defer(ephemeral=True)
    amount_str: str = amount
    amount = amount.replace(",", "")

    if not re.match(AMOUNT_PATTERN, amount):
        await amount_invalid(ctx, amount_str)
        return

    amount: int = Utils.parse_amount(amount)

    if not Utils.check_amount_limits(amount):
        await amount_outside_limits(ctx, amount_str)
        return
    given_staff = staff
    staff = await get_staff_member_from_discord_id(str(given_staff.id))

    if not staff:
        await staff_not_found(ctx, given_staff)
        logging.warning(
            f"Command executor not staff member, cannot complete transaction!")
        return

    transaction_type = "event"

    if not reason:
        await ctx.send(f"A reason is required for an {transaction_type}! {transaction_type.capitalize} logging was not completed.")
        logging.info(
            f"No reason was given for the {transaction_type}. Stopping transaction")
        return

    await insert_transaction(ctx, transaction_type, user, staff, amount, reason)
    await ctx.send(f"{transaction_type.capitalize()} Logged! Member {user.mention} donated **{amount:,}gp** via the event {reason}", ephemeral=True)

    logging.info(
        f"Transaction successfully logged: {transaction_type} for {user}")

# Common function for donation and payout


async def log_transaction(ctx: SlashContext, staff: OptionType.USER, user: OptionType.USER, amount: str, transaction_type: str, reason: str = None):
    logging.info(
        f"Logging transaction: type={transaction_type}, user={user}, amount={amount}")
    await ctx.defer(ephemeral=True)
    amount_str: str = amount
    amount = amount.replace(",", "")

    if not re.match(AMOUNT_PATTERN, amount):
        await amount_invalid(ctx, amount_str)
        return

    amount: int = Utils.parse_amount(amount)

    if not Utils.check_amount_limits(amount):
        await amount_outside_limits(ctx, amount_str)
        return
    given_staff = staff
    staff = await get_staff_member_from_discord_id(str(given_staff.id))

    if not staff:
        await staff_not_found(ctx, given_staff)
        logging.warning(
            f"Command executor not staff member, cannot complete transaction!")
        return

    logging.info(
        f"Trying to get balance from {staff}. his finances {staff.get("finances")}.")
    balance = staff.get("finances")["currentBalance"] or 0

    adj_balance_amount = amount

    # Payouts must exist in the balance
    if transaction_type in NEGATIVE_TRANSACTIONS:
        # Ensures staff member has the funds to payout to user
        if balance < amount:
            await ctx.send(f"<@!{staff.get('discordId')}> does not have the balance for this {transaction_type}. Current balance is **{balance:,}**, Requested amount is **{amount:,}**")
            return

        adj_balance_amount *= -1

        # Also ensures there is a reason
        if not reason:
            await ctx.send(f"A reason is required for a {transaction_type}! {transaction_type.capitalize} was not completed.")
            logging.info(
                f"No reason was given for the {transaction_type}. Stopping transaction")
            return

    balance += adj_balance_amount  # New balance
    set_staff_balance(staff, balance)
    logging.info(f"{staff}'s new balance is {balance:,}")
    await insert_transaction(ctx, transaction_type, user, staff, amount, reason)
    verb = "received" if transaction_type in NEGATIVE_TRANSACTIONS else "gave"
    action_string = f" for **{reason}**." if transaction_type in NEGATIVE_TRANSACTIONS else "."
    await ctx.send(f"{transaction_type.capitalize()} Logged! Member {user.mention} {verb} **{amount:,}** OSRS gold{action_string} \n\n<@!{staff.get('discordId')}>'s balance is now **{balance:,}**", ephemeral=True)

    logging.info(
        f"Transaction successfully logged: {transaction_type} for {user}")


# Command that gets the balance for a staff member
@slash_command(name="balance", description="Gets balance for a given staff member")
@slash_option(
    name="staff",
    description="Staff member",
    required=False,
    opt_type=OptionType.USER
)
async def get_balance_command(ctx: SlashContext, staff: OptionType.USER = None):
    await ctx.defer(ephemeral=True)
    user = staff
    discord_id = user.id if user else ctx.author_id
    staff = await get_staff_member_from_discord_id(str(discord_id))

    if not staff:
        await staff_not_found(ctx, user)
        logging.warning(
            f"Command executor not staff member, cannot complete transaction!")
        return

    logging.info(
        f"Trying to get balance from {staff}. his finances {staff.get("finances")}.")
    balance = staff.get("finances")["currentBalance"] or 0

    if balance is not None:
        await ctx.send(f"<@!{staff.get('discordId')}>'s current balance is **{balance:,}**", ephemeral=True)


# Command that gets the total balance for all staff and broken down by staff member
@slash_command(name="totalbalance", description="Gets total balance of all staff members")
async def total_balance_command(ctx: SlashContext):
    await ctx.defer(ephemeral=True)

    total_balance_str = get_total_balance()

    await ctx.send(total_balance_str, ephemeral=True)


# Command that sets a staff member's balance
@slash_command(name="setbalance", description="Set a staff member's balance")
@slash_option(
    name="staff",
    description="Staff member that will have the new balance",
    required=True,
    opt_type=OptionType.USER
)
@slash_option(
    name="amount",
    description="Amount of OSRS gold. Same logic as in game (Between 1 gp and 5 billion gp)",
    required=True,
    opt_type=OptionType.STRING
)
async def set_balance_command(ctx: SlashContext, staff: OptionType.USER, amount: str):
    await ctx.defer(ephemeral=True)
    amount_str: str = amount
    amount = amount.replace(",", "")

    if not re.match(AMOUNT_PATTERN, amount):
        await amount_invalid(ctx, amount_str)
        return

    amount = Utils.parse_amount(amount)

    if not Utils.check_amount_limits(amount):
        await amount_outside_limits(ctx, amount_str)
        return

    user = staff
    staff = await get_staff_member_from_discord_id(str(user.id))

    if not staff:
        await staff_not_found(ctx, user)
        logging.warning(
            f"Command executor not staff member, cannot complete transaction!")
        return

    set_staff_balance(staff, amount)
    await ctx.send(f"<@!{staff.get('discordId')}>'s balance has been set to **{amount:,}**", ephemeral=True)


# Command that transfers from one staff member's balance to another's
@slash_command(name="transfer", description="Transfers balance from one staff member to another.")
@slash_option(
    name="from_staff",
    description="Staff member that funds would be transfered FROM.",
    required=True,
    opt_type=OptionType.USER
)
@slash_option(
    name="to_staff",
    description="Staff member that funds would be transfered TO.",
    required=True,
    opt_type=OptionType.USER
)
@slash_option(
    name="amount",
    description="Amount of OSRS gold. Same logic as in game (Between 1 gp and 5 billion gp)",
    required=True,
    opt_type=OptionType.STRING
)
async def transfer_command(ctx: SlashContext, from_staff: OptionType.USER, to_staff: OptionType.USER, amount: str):
    await ctx.defer(ephemeral=True)
    await log_transfer(ctx, from_staff, to_staff, amount)


# Command that logs player event
@slash_command(name="event", description="Log an event")
@slash_option(
    name="staff",
    description="Staff member logging this event",
    required=True,
    opt_type=OptionType.USER
)
@slash_option(
    name="member",
    description="Clan member donating the item/gold/bonds to the event winnings",
    required=True,
    opt_type=OptionType.USER
)
@slash_option(
    name="amount",
    description="Amount of OSRS gold. Same logic as in game (Between 1 gp and 5 billion gp)",
    required=True,
    opt_type=OptionType.STRING
)
@slash_option(
    name="event_desc",
    description="Short description of the event, for traceability purposes.",
    required=True,
    opt_type=OptionType.STRING
)
async def event_command(ctx: SlashContext, staff: OptionType.USER, member: OptionType.USER, amount: str, event_desc: str):
    await log_event(ctx, staff, member, amount, event_desc)


# Command that logs player donations
@slash_command(name="donation", description="Log a donation")
@slash_option(
    name="staff",
    description="Staff member receiving this donation",
    required=True,
    opt_type=OptionType.USER
)
@slash_option(
    name="member",
    description="Clan member donating the item/gold/bonds",
    required=True,
    opt_type=OptionType.USER
)
@slash_option(
    name="amount",
    description="Amount of OSRS gold. Same logic as in game (Between 1 gp and 5 billion gp)",
    required=True,
    opt_type=OptionType.STRING
)
async def donation_command(ctx: SlashContext, staff: OptionType.USER, member: OptionType.USER, amount: str):
    await log_transaction(ctx, staff, member, amount, "donation")


# Command that logs player buyins
@slash_command(name="buyin", description="Log a buyin")
@slash_option(
    name="staff",
    description="Staff member receiving this buy in",
    required=True,
    opt_type=OptionType.USER
)
@slash_option(
    name="member",
    description="Clan member donating the item/gold/bonds",
    required=True,
    opt_type=OptionType.USER
)
@slash_option(
    name="amount",
    description="Amount of OSRS gold. Same logic as in game (Between 1 gp and 5 billion gp)",
    required=True,
    opt_type=OptionType.STRING
)
async def buy_in_command(ctx: SlashContext, staff: OptionType.USER, member: OptionType.USER, amount: str):
    await log_transaction(ctx, staff, member, amount, "buy in")


# Command that logs player payouts
@slash_command(name="payout", description="Log a payout")
@slash_option(
    name="staff",
    description="Staff member completing this payout",
    required=True,
    opt_type=OptionType.USER
)
@slash_option(
    name="member",
    description="Clan member receiving this payout",
    required=True,
    opt_type=OptionType.USER
)
@slash_option(
    name="amount",
    description="Amount of OSRS gold. Same logic as in game (Between 1 gp and 5 billion gp)",
    required=True,
    opt_type=OptionType.STRING
)
@slash_option(
    name="reason",
    description="Why is this member getting gold?",
    required=True,
    opt_type=OptionType.STRING
)
async def payout_command(ctx: SlashContext, staff: OptionType.USER, member: OptionType.USER, amount: str, reason: str):
    await log_transaction(ctx, staff, member, amount, "payout", reason)


# Command that gets last 5 payouts
@slash_command(name="recent_transactions", description="Get the last five logs for a transaction type.")
@slash_option(
    name="transaction_type",
    description="Type of transaction you want to see recents of.",
    required=True,
    opt_type=OptionType.STRING,
    choices=[
        SlashCommandChoice(name="donations", value="donation"),
        SlashCommandChoice(name="payouts", value="payout")
    ]
)
async def recent_transactions_command(ctx: SlashContext, transaction_type: str):
    await ctx.defer(ephemeral=True)

    results = db.transaction_log.aggregate([
        {
            "$lookup": {
                "from": "members",
                "localField": "member_id",
                "foreignField": "_id",
                "as": "member_info"
            }
        },
        {
            "$unwind": {
                "path": "$member_info",
                "preserveNullAndEmptyArrays": True
            }
        },
        {
            "$lookup": {
                "from": "members",
                "localField": "staff_id",
                "foreignField": "_id",
                "as": "staff_info"
            }
        },
        {
            "$unwind": {
                "path": "$staff_info",
                "preserveNullAndEmptyArrays": True
            }
        },
        {
            "$match": {
                "type": {
                    "$eq": transaction_type
                }
            }
        },
        {
            "$project": {
                "_id": 0,
                "discordId": "$member_info.discordId",
                "staff_discordId": "$staff_info.discordId",
                "type": 1,
                "amount": 1,
                "donation_time": 1,
                "reason": 1
            }
        },
        {
            "$sort": {
                "donation_time": -1
            }
        },
        {"$limit": 10}
    ])

    verb = "received" if transaction_type in NEGATIVE_TRANSACTIONS else "donated"
    transaction_list = ""
    for transaction in results:
        logging.info(transaction)
        reason = f" for {transaction["reason"] or "NO REASON GIVEN"}" if transaction_type in NEGATIVE_TRANSACTIONS else ""
        transaction_list += f"<@!{transaction["discordId"]}> {verb} **{transaction["amount"]:,}**{reason}. Logged by <@!{transaction["staff_discordId"]}>\n"
    transaction_list = transaction_list.rstrip("\n")

    await ctx.send(f"Got some results for ya!\n{transaction_list}")


# Command that provides results for the given month/year
@slash_command(name="monthresults", description="Get transaction information for a given month")
@slash_option(
    name="month",
    description="Calendar month (1-12)",
    required=True,
    opt_type=OptionType.INTEGER,
    min_value=1,
    max_value=12
)
@slash_option(
    name="year",
    description="Calendar year (2025<)",
    required=True,
    opt_type=OptionType.INTEGER,
    min_value=2025,
    max_value=datetime.now().year
)
async def transaction_results_command(ctx: SlashContext, month: int, year: int):
    if not Utils.check_month_input(month):
        await ctx.send(f"Given month {month} is not a valid month number. (1 - 12 is allowed)")
        return

    start_date = datetime(year, month, 1)
    if month == 12:
        end_date = datetime(year + 1, 1, 1)
    else:
        end_date = datetime(year, month + 1, 1)

    # Query
    results = db.transaction_log.aggregate([
        {
            "$lookup": {
                "from": "members",
                "localField": "member_id",
                "foreignField": "_id",
                "as": "member_info"
            }
        },
        {
            "$unwind": {
                "path": "$member_info",
                "preserveNullAndEmptyArrays": True
            }
        },
        {
            "$lookup": {
                "from": "members",
                "localField": "staff_id",
                "foreignField": "_id",
                "as": "staff_info"
            }
        },
        {
            "$unwind": {
                "path": "$staff_info",
                "preserveNullAndEmptyArrays": True
            }
        },
        {
            "$match": {
                "donation_time": {
                    "$gte": start_date,
                    "$lt": end_date
                }
            }
        },
        {
            "$project": {
                "_id": 0,
                "discordUsername": "$member_info.discordUsername",
                "staff_discordUsername": "$staff_info.discordUsername",
                "type": 1,
                "amount": 1,
                "donation_time": 1,
                "reason": 1
            }
        },
        {
            "$sort": {
                "amount": -1
            }
        }
    ])
    overall_balance = 0
    total_donations = 0
    total_payouts = 0

    for transaction in results:
        logging.info(transaction)
        if transaction["type"] == "donation":
            total_donations += transaction["amount"]
            overall_balance += transaction["amount"]
        else:
            total_payouts += transaction["amount"]
            overall_balance -= transaction["amount"]

    await ctx.send(f"Results for {month}/{year}\n\n Total donations: {total_donations:,}\n Total payouts: {total_payouts:,}\n Month's result: **{overall_balance:,}**", ephemeral=True)

 # Global message IDs
top_donations_message_id = None
recent_transactions_message_id = None
recent_events_message_id = None


@slash_command(name="update_donation_leaderboard", description="Update the Top Donations message with the current timestamp")
async def update_top_donations(ctx):
    global top_donations_message_id

    if top_donations_message_id is None:
        await ctx.send("No top donations message found. Please wait until the bot has posted the initial message.", ephemeral=True)
        return

    top_donations_message = get_top_donations()
    top_donations_channel = await bot.fetch_channel(int(os.getenv("TOP_DONATIONS_CHANNEL_ID")))
    message = await top_donations_channel.fetch_message(top_donations_message_id)
    await message.edit(content=top_donations_message)


@slash_command(name="update_recent_transactions", description="Update the Recent Transactions message")
async def update_recent_transactions(ctx: SlashContext):
    global recent_transactions_message_id

    if recent_transactions_message_id is None:
        await ctx.send("No recent transactions message found. Please wait until the bot has posted the initial message.", ephemeral=True)
        return

    message_content = get_recent_transactions()
    channel = await bot.fetch_channel(int(os.getenv("RECENT_TRANSACTIONS_CHANNEL_ID")))
    message = await channel.fetch_message(recent_transactions_message_id)
    await message.edit(content=message_content)


@slash_command(name="update_recent_events", description="Update the Recent Transactions message")
async def update_recent_events(ctx: SlashContext):
    global recent_events_message_id

    if recent_events_message_id is None:
        await ctx.send("No recent transactions message found. Please wait until the bot has posted the initial message.", ephemeral=True)
        return

    message_content = get_recent_events()
    channel = await bot.fetch_channel(int(os.getenv("RECENT_TRANSACTIONS_CHANNEL_ID")))
    message = await channel.fetch_message(recent_events_message_id)
    await message.edit(content=message_content)

@slash_command(
    name="blacklist",
    description="Manage blacklisted discord users.",
    sub_cmd_name="add",
    sub_cmd_description="Add discord user to blacklist",
)
@slash_option(
    name="discord_id",
    description="Discord ID for the user you want",
    required=True,
    opt_type=OptionType.STRING,
    min_length=17,
    max_length=20
)
@slash_option(
    name="reason",
    description="Reason for adding the user to the blacklist",
    required=True,
    opt_type=OptionType.STRING
)
async def blacklist_add_command(ctx: SlashContext, discord_id: str, reason: str):
    if not Utils.is_valid_discord_id(discord_id):
        await ctx.send(f"Discord ID {discord_id} is not a valid ID. The blacklist addition was cancelled.", ephemeral=True)
        return

    staff = await get_staff_member_from_discord_id(str(ctx.author_id))

    if not staff:
        await staff_not_found(ctx, ctx.author)
        logging.warning(
            f"Command executor not staff member, cannot complete transaction!")
        return
    
    if not reason:
        await ctx.send(f"No reason given. The blacklist addition was cancelled.", ephemeral=True)
        return
    
    result = db.blacklist.find_one({"discord_id": discord_id})

    if result:
        await ctx.send(f"Player already logged in blacklist. The blacklist addition was cancelled.", ephemeral=True)
        return

    new_blacklist = {
        "discord_id": discord_id,
        "reason": reason,
        "time": datetime.now(timezone.utc),
        "staff_id": staff["_id"],
    }

    result = db.blacklist.insert_one(new_blacklist)
    print(f"New blacklist added {result}")
    await ctx.send(f"User with Discord ID `{discord_id}` added to blacklist for `{reason}`")
    

@listen(MemberAdd)
async def on_member_join(event: MemberAdd):
    joined_member: Member = event.member
    discord_id = str(joined_member.id)

    print(f"{discord_id} has joined the server. Checking if user is on the blacklist...")

    result = db.blacklist.aggregate([
        {"$match": {"discord_id": discord_id}},  # or "discordId" here if the blacklisted user also uses that field name
        {
            "$lookup": {
                "from": "members",
                "localField": "staff_id",
                "foreignField": "_id",
                "as": "staff_info"
            }
        },
        {"$unwind": "$staff_info"},
        {
            "$project": {
                "discord_id": 1,
                "reason": 1,
                "time": 1,
                "staff_id": 1,
                "staff_discord_id": "$staff_info.discordId"
            }
        }
    ])

    result = next(result, None)


    if result:
        print(f"User found in blacklist! Alerting staff team.")
        reason = result.get("reason", "No reason provided.")
        timestamp = result.get("time", "")
        staff_discord_id = result.get("staff_discord_id", "")
        
        # Format for Discord relative time (must be in seconds)
        if isinstance(timestamp, datetime):
            if timestamp.tzinfo is None:
                # Assume it's already UTC if tz is missing
                print("⚠️ Naive datetime detected — assuming UTC.")
                timestamp = timestamp.replace(tzinfo=timezone.utc)
            else:
                # Convert to UTC to be safe
                timestamp = timestamp.astimezone(timezone.utc)
                
            unix_ts = int(timestamp.timestamp())
            relative_time = f"<t:{unix_ts}:R>"
        else:
            relative_time = "Unknown time"

        # # DM the user
        # try:
        #     await joined_member.send(
        #         f"You were removed from the server for the following reason:\n**{reason}**"
        #     )
        # except Exception as e:
        #     print(f"Could not DM {discord_id}: {e}")

        # # Kick the user
        # try:
        #     await joined_member.kick(reason=f"Blacklisted: {reason}")
        #     print(f"Kicked blacklisted user {discord_id}.")
        # except Exception as e:
        #     print(f"Kick failed for {discord_id}: {e}")

        # Log to the channel
        channel_id = int(os.getenv("BLACKLIST_CHANNEL_ID", "0"))
        if channel_id:
            try:
                log_channel = await event.guild.fetch_channel(channel_id)
                await log_channel.send(
                    f"🚫 **Blacklisted user joined the discord**\n"
                    f"> **User**: <@!{discord_id}>\n"
                    f"> **Discord ID**: `{discord_id}`\n"
                    f"> **Reason**: {reason}\n"
                    f"> **Blacklisted**: {relative_time}\n"
                    f"> **Blacklisted By**: <@!{staff_discord_id}>\n"
                    f"<@&1219343040318144532>"
                )
            except Exception as e:
                print(f"Failed to post to blacklist log channel: {e}")
    else:
        print(f"User {discord_id} is not blacklisted.")
    
    
bot = Client(intents=Intents.ALL)

@listen()
async def on_ready():
    global top_donations_message_id
    global recent_transactions_message_id
    global recent_events_message_id
    bot.load_extension("interactions.ext.jurigged", poll=True)
    logging.info("Bot is ready")
    logging.info(f"This bot is owned by {bot.owner}")

    # ---- TOP DONATIONS ----
    TOP_DONATIONS_CHANNEL_ID = int(os.getenv("TOP_DONATIONS_CHANNEL_ID"))
    top_donations_channel = await bot.fetch_channel(TOP_DONATIONS_CHANNEL_ID)

    if top_donations_channel:
        messages = [msg async for msg in top_donations_channel.history(limit=100)]

        for msg in messages:
            if msg.author.id == bot.user.id and "Donor" in msg.content:
                top_donations_message_id = msg.id
                logging.info(
                    f"Found existing top donations message with ID: {top_donations_message_id}")
                break

        if not top_donations_message_id:
            content = get_top_donations()
            sent_message = await top_donations_channel.send(content)
            top_donations_message_id = sent_message.id
            logging.info(
                f"Sent new top donations message with ID: {top_donations_message_id}")
    else:
        logging.warning("Could not find the top donations channel.")

    # ---- RECENT TRANSACTIONS ----
    RECENT_TRANSACTIONS_CHANNEL_ID = int(
        os.getenv("RECENT_TRANSACTIONS_CHANNEL_ID"))
    recent_transactions_channel = await bot.fetch_channel(RECENT_TRANSACTIONS_CHANNEL_ID)

    if recent_transactions_channel:
        messages = [msg async for msg in recent_transactions_channel.history(limit=100)]

        for msg in messages:
            if not recent_transactions_message_id and msg.author.id == bot.user.id and "diff" in msg.content:
                recent_transactions_message_id = msg.id
                logging.info(
                    f"Found existing recent transactions message with ID: {recent_transactions_message_id}")

            if not recent_events_message_id and msg.author.id == bot.user.id and "fix" in msg.content:
                recent_events_message_id = msg.id
                logging.info(
                    f"Found existing recent events message with ID: {recent_events_message_id}")

        if not recent_transactions_message_id:
            content = get_recent_transactions()
            logging.info(content)
            sent_message = await recent_transactions_channel.send(content)
            recent_transactions_message_id = sent_message.id
            logging.info(
                f"Sent new recent transactions message with ID: {recent_transactions_message_id}")

        if not recent_events_message_id:
            content = get_recent_events()
            logging.info(content)
            sent_message = await recent_transactions_channel.send(content)
            recent_events_message_id = sent_message.id
            logging.info(
                f"Sent new recent events message with ID: {recent_events_message_id}")
    else:
        logging.warning("Could not find the recent transactions channel.")


if __name__ == "__main__":
    logging.info("Starting bot...")
    assert os.getenv("BOT_TOKEN"), "Missing DISCORD_TOKEN!"
    bot.start(os.getenv("BOT_TOKEN"))
