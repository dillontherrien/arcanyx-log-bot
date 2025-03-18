import asyncio
import os
import re
from dotenv import load_dotenv
from interactions import Client, Intents, SlashContext, listen, slash_command, slash_option, OptionType

# Loads environment variables
load_dotenv()

bot = Client(intents=Intents.DEFAULT)

def parse_amount(amount: str) -> int:
    """
    Takes the valid input and multiplys it based on letter if present.
    """
    multipliers = {'k': 1_000, 'm': 1_000_000, 'b': 1_000_000_000} # Underscores are for readability
    multiplier = amount[-1].lower()

    if multiplier in multipliers:
        return int(amount[:-1]) * multipliers[multiplier]
    
    return int(amount)

@listen()
async def on_ready():
    print("Ready")
    print(f"This bot is owned by {bot.owner}")

# Basic command
# @slash_command(name="my_command", description="My first command :)")
# async def my_command_function(ctx: SlashContext):
#     await ctx.send("Hello World")

# Regex pattern to ensure OSRS gp logic is enforced
AMOUNT_PATTERN = r"^\d*[kmbKMB]?$"

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
async def my_command_function(ctx: SlashContext, user: str, amount: str):
    amount = amount.replace(",", "")
    
    # Checks that the input amount is valid format
    if not re.match(AMOUNT_PATTERN, amount):
        await ctx.send(f"Amount given ({amount}) is not valid. Please follow same logic in game for typing amounts (eg. 42244, 24m, 11k)")
        return
    
    amount = parse_amount(amount)
        
    await ctx.send(f"You input {amount}")

bot.start(os.getenv("BOT_TOKEN"))