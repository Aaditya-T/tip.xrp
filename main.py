import xrpl
import discord
import asyncio
import dotenv
import os
import logging
from discord import app_commands
import xumm
import helper
import random

# Load the .env file
dotenv.load_dotenv()

TOKEN = os.getenv("token")
XUMM_TOKEN = os.getenv("XUMM_TOKEN")
XUMM_SECRET = os.getenv("XUMM_SECRET")
DESTADDR = "rbKoFeFtQr2cRMK2jRwhgTa1US9KU6v4L"

logging.basicConfig(level=logging.INFO)


class aclient(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        intents.members = True
        intents.messages = True
        super().__init__(intents=intents)
        self.synced = False

    async def on_ready(self):
        await self.wait_until_ready()
        await tree.sync()
        print(f"Logged in as {self.user}")


client = aclient()
tree = app_commands.CommandTree(client)


@tree.command(name="ping", description="Ping the bot")
async def ping(interaction: discord.Interaction):
    latency = round(client.latency * 1000)
    await interaction.response.send_message(f"Pong! ({latency}ms)")


@tree.command(name="register", description="Verify your XRP address")
async def verify(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    rnum = helper.registerUser(interaction.user.id)
    await interaction.followup.send(
        content="You have been registered! Your destination tag is: " + str(rnum), ephemeral=True
    )

@tree.command(name="wallet", description="Get your XRP address")
async def wallet(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    userData = helper.getUser(interaction.user.id)
    if userData is None:
        await interaction.followup.send(content="You are not registered!", ephemeral=True)
        return
    embed = discord.Embed(title="Wallet", color=0x00FF00)
    embed.add_field(name="Destination Tag", value=str(userData["dest"]))
    embed.add_field(name="XRP Balance", value=str(userData["xrpBalance"]))
    tlsString = ""
    for tl in userData["tls"]:
        cur = tl['currency']
        if len(cur) > 3:
            cur = xrpl.utils.hex_to_str(cur)
        tlsString += f"{cur} {tl['value']} {tl['issuer']}\n"
    if tlsString != "":
        embed.add_field(name="Trustlines", value=tlsString)
    embed.add_field(name="Deposit", value=f"Use `/deposit <amount>` to deposit XRP to your account or you can directly pay to the address given below and destination tag given above\nAddress: {DESTADDR}", inline=False)
    await interaction.followup.send(embed=embed, ephemeral=True)

@tree.command(name="deposit", description="Deposit XRP to your account")
async def deposit(interaction: discord.Interaction, amount: float):
    userData = helper.getUser(interaction.user.id)
    if userData is None:
        await interaction.response.send_message("You are not registered!", ephemeral=True)
        return
    destTag = userData["dest"]
    if amount <= 0:
        await interaction.response.send_message("Invalid amount", ephemeral=True)
        return
    sdk = xumm.XummSdk(XUMM_TOKEN, XUMM_SECRET)
    payload = {
            "TransactionType": "Payment",
            "Destination": DESTADDR,
            "DestinationTag": destTag,
            "Amount": xrpl.utils.xrp_to_drops(amount),
        }
    response = sdk.payload.create(payload)
    qrcode = response.refs.qr_png
    link = response.next.always
    embed = discord.Embed(title="Deposit XRP", description=f"Scan the QR code or [click here]({link}) to deposit xrp to your account!", color=random.randint(0, 0xFFFFFF))
    embed.add_field(name="Amount", value=str(amount))
    embed.add_field(name="Destination Tag", value=str(destTag))
    embed.add_field(name="NOTE", value="You can directly pay to the address and destination tag above, but please make sure to include the correct destination tag!")
    embed.set_image(url=qrcode)
    await interaction.response.send_message(embed=embed, ephemeral=True)

client.run(TOKEN)
