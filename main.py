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
from typing import Literal

# Load the .env file
dotenv.load_dotenv()

TOKEN = os.getenv("token")
XUMM_TOKEN = os.getenv("XUMM_TOKEN")
XUMM_SECRET = os.getenv("XUMM_SECRET")
DESTADDR = "rJAFQ2d6mUTgHHtLogPx5BB5NRT97ASFDy"

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
        content="You have been registered! Your destination tag is: " + str(rnum),
        ephemeral=True,
    )


@tree.command(name="wallet", description="Get your XRP address")
async def wallet(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    userData = helper.getUser(interaction.user.id)
    if userData is None:
        await interaction.followup.send(
            content="You are not registered!", ephemeral=True
        )
        return
    embed = discord.Embed(title="Wallet", color=0x00FF00)
    embed.add_field(name="Destination Tag", value=str(userData["dest"]))
    embed.add_field(name="XRP Balance", value=str(round(userData["xrpBalance"], 6)))
    tlsString = ""
    for tl in userData["tls"]:
        cur = tl["currency"]
        if len(cur) > 3:
            cur = xrpl.utils.hex_to_str(cur)
        tlsString += f"{cur} {tl['value']}\n"
    if tlsString != "":
        embed.add_field(name="Trustlines", value=tlsString)
    embed.add_field(
        name="Deposit",
        value=f"Use `/deposit <amount>` to deposit XRP to your account or you can directly pay to the address given below and destination tag given above\nAddress: {DESTADDR}",
        inline=False,
    )
    await interaction.followup.send(embed=embed, ephemeral=True)

@tree.command(name="send", description="Send a currency to another user")
async def send(interaction: discord.Interaction, amount: float, currency: Literal["XRP", "SOLO", "CSC", "USD", "ZRP"], receiver: discord.User):
    curMain = currency
    if len(curMain) > 3:
        curMain = helper.str_to_hex(currency)
    userData = helper.getUser(interaction.user.id)
    if userData is None:
        await interaction.response.send_message(
            "You are not registered!", ephemeral=True
        )
        return
    if amount <= 0:
        await interaction.response.send_message("Invalid amount", ephemeral=True)
        return
    if currency == "XRP":
        if userData["xrpBalance"] < amount:
            await interaction.response.send_message("Insufficient balance", ephemeral=True)
            return
        sent = helper.sendXRP(str(interaction.user.id), str(receiver.id), amount)
        if not sent:
            await interaction.response.send_message("Failed to send XRP", ephemeral=True)
            return
    else:
        for tl in userData["tls"]:
            if tl["currency"] == curMain:
                if tl["value"] < amount:
                    await interaction.response.send_message("Insufficient balance", ephemeral=True)
                    return
                sent = helper.sendTL(str(interaction.user.id), str(receiver.id), curMain, amount)
                if not sent:
                    await interaction.response.send_message("Failed to send", ephemeral=True)
                    return
                break
        else:
            await interaction.response.send_message("You don't have a trustline for this currency", ephemeral=True)
            return
    await interaction.response.send_message(f"Sent {amount} {currency} to {receiver.mention}", ephemeral=True)

@tree.command(name="deposit", description="Deposit any currency to your account")
async def deposit(interaction: discord.Interaction, amount: float, currency: Literal["XRP", "SOLO", "CSC", "USD", "ZRP"]):
    curMain = currency
    if len(curMain) > 3:
        curMain = helper.str_to_hex(currency)
    curData = helper.getCurData(curMain)
    userData = helper.getUser(interaction.user.id)
    if userData is None:
        await interaction.response.send_message(
            "You are not registered!", ephemeral=True
        )
        return
    desttag = userData["dest"]
    if amount <= 0:
        await interaction.response.send_message("Invalid amount", ephemeral=True)
        return
    sdk = xumm.XummSdk(XUMM_TOKEN, XUMM_SECRET)
    if currency == "XRP":
        amt = xrpl.utils.xrp_to_drops(amount)
    else:
        amt = {
            "currency": curMain,
            "issuer": curData["issuer"],
            "value": amount,            
        }
    payload = {
        "TransactionType": "Payment",
        "Destination": DESTADDR,
        "DestinationTag": desttag,
        "Amount": amt,
    }
    response = sdk.payload.create(payload)
    qrcode = response.refs.qr_png
    link = response.next.always
    embed = discord.Embed(
        title=f"Deposit {currency}",
        description=f"Scan the QR code or [click here]({link}) to deposit {currency} to your account!",
        color=random.randint(0, 0xFFFFFF),
    )
    embed.add_field(name="Amount", value=str(amount))
    embed.add_field(name="Destination Tag", value=str(desttag))
    embed.add_field(
        name="NOTE",
        value="You can directly pay to the address and destination tag above, but please make sure to include the correct destination tag!",
    )
    embed.set_image(url=qrcode)
    if currency != "XRP":
        embed.set_footer(text=f"Currency: {currency}", icon_url=curData["image"])
    else:
        embed.set_footer(text=f"Currency: {currency}")
    await interaction.response.send_message(embed=embed, ephemeral=True)

@tree.command(name="withdraw", description="Withdraw any currency from your account to your wallet")
async def withdraw(interaction: discord.Interaction, amount: float, currency: Literal["XRP", "SOLO", "CSC", "USD", "ZRP"], address: str, desttag: int = None):
    await interaction.response.defer(ephemeral=True)
    curMain = currency
    if len(curMain) > 3:
        curMain = helper.str_to_hex(currency)
    userData = helper.getUser(interaction.user.id)
    if userData is None:
        await interaction.followup.send(
            "You are not registered!", ephemeral=True
        )
        return
    if amount <= 0:
        await interaction.followup.send("Invalid amount", ephemeral=True)
        return
    if currency == "XRP":
        if userData["xrpBalance"] < amount:
            await interaction.followup.send("Insufficient balance", ephemeral=True)
            return
        # sent = helper.send_xrp_to_wallet(address, amount, str(interaction.user.id), desttag)
        loop = asyncio.get_event_loop()
        sent = await loop.run_in_executor(None, helper.send_xrp_to_wallet, address, amount, str(interaction.user.id), desttag)
        if not sent:
            await interaction.followup.send("Failed to withdraw XRP", ephemeral=True)
            return
    else:
        for tl in userData["tls"]:
            if tl["currency"] == curMain:
                if tl["value"] < amount:
                    await interaction.followup.send("Insufficient balance", ephemeral=True)
                    return
                # sent = helper.send_tl_to_wallet(address, amount, str(interaction.user.id), curMain, tl["issuer"], desttag)
                loop = asyncio.get_event_loop()
                sent = await loop.run_in_executor(None, helper.send_tl_to_wallet, address, amount, str(interaction.user.id), curMain, tl["issuer"], desttag)
                if not sent:
                    await interaction.followup.send("Failed to withdraw", ephemeral=True)
                    return
                break
        else:
            await interaction.followup.send("You don't have a trustline for this currency", ephemeral=True)
            return
    await interaction.followup.send(f"Withdrew {amount} {currency} to your wallet", ephemeral=True)

@tree.command(name="swap", description="Swap currencies using AMM")
async def swap(interaction: discord.Interaction, amount: float, fromcurrency: Literal["XRP", "SOLO", "CSC", "USD", "ZRP"], tocurrency: Literal["XRP", "SOLO", "CSC", "USD", "ZRP"]):
    curMain = fromcurrency
    if len(curMain) > 3:
        curMain = helper.str_to_hex(fromcurrency)
    userData = helper.getUser(interaction.user.id)
    if userData is None:
        await interaction.response.send_message(
            "You are not registered!", ephemeral=True
        )
        return
    if amount <= 0:
        await interaction.response.send_message("Invalid amount", ephemeral=True)
        return
    if fromcurrency == tocurrency:
        await interaction.response.send_message("Cannot swap same currency", ephemeral=True)
        return
    if fromcurrency != "XRP":
        for tl in userData["tls"]:
            if tl["currency"] == curMain:
                if tl["value"] < amount:
                    await interaction.response.send_message("Insufficient balance", ephemeral=True)
                    return
                break
        else:
            await interaction.response.send_message("You don't have a trustline for this currency", ephemeral=True)
            return
    else:
        if userData["xrpBalance"] < amount:
            await interaction.response.send_message("Insufficient balance", ephemeral=True)
            return
    clientXrpl = xrpl.clients.JsonRpcClient("https://xrplcluster.com/")
    if tocurrency == "XRP":
        curData = helper.getCurData(curMain)
        # ammStat = await helper.get_swap_stats(clientXrpl,curMain,curData["issuer"], amount, True)
        loop = asyncio.get_event_loop()
        ammStat = await loop.run_in_executor(None, helper.get_swap_stats, clientXrpl, curMain, curData["issuer"], amount, False)
        if ammStat is None:
            await interaction.response.send_message("Failed to swap", ephemeral=True)
            return
    else:
        if len(tocurrency) > 3:
            curMain = helper.str_to_hex(tocurrency)
        else:
            curMain = tocurrency
        curData = helper.getCurData(curMain)
        # ammStat = await helper.get_swap_stats(clientXrpl,curMain,curData["issuer"], amount, False)
        loop = asyncio.get_event_loop()
        ammStat = await loop.run_in_executor(None, helper.get_swap_stats, clientXrpl, curMain, curData["issuer"], amount, True)
        if ammStat is None:
            await interaction.response.send_message("Failed to swap", ephemeral=True)
            return
    if ammStat:
        embed = discord.Embed(title="Swap Details", color=0x00FF00, description="Please confirm the swap")
        embed.add_field(name="From", value=f"{amount} {fromcurrency}")
        embed.add_field(name="To", value=f"{ammStat} {tocurrency}")
        embed.add_field(name="Slippage", value="1.5%")
        button = discord.ui.Button(style=discord.ButtonStyle.green, label="Confirm", custom_id="confirm_swap")
        async def callback(interaction: discord.Interaction):
            await interaction.response.defer(ephemeral=True)
            loop = asyncio.get_event_loop()
            if fromcurrency == "XRP":
                if len(tocurrency) > 3:
                    curMain = helper.str_to_hex(tocurrency)
                else:
                    curMain = tocurrency
                curData = helper.getCurData(curMain)
                sent = await loop.run_in_executor(None, helper.execute_swap, clientXrpl, curMain, curData["issuer"], amount, False, str(interaction.user.id))
            else:
                if len(fromcurrency) > 3:
                    curMain = helper.str_to_hex(fromcurrency)
                else:    
                    curMain = fromcurrency
                curData = helper.getCurData(curMain)
                sent = await loop.run_in_executor(None, helper.execute_swap, clientXrpl, curMain, curData["issuer"], amount, True, str(interaction.user.id))
            if not sent:
                await interaction.response.send_message("Failed to swap", ephemeral=True)
                return
            await interaction.followup.edit_message(content="Swapped successfully", embed=None, view=None, message_id=interaction.message.id)
        button.callback = callback
        view = discord.ui.View()
        view.add_item(button)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

@tree.command(name="supported", description="List of supported currencies")
async def supported(interaction: discord.Interaction):
    supported = helper.getSupported() # [{"name": "XRP", "code": "XRP", "issuer": ""}, ...]
    embed = discord.Embed(title="Supported Currencies", color=0x00FF00, description="XRP is of course supported!")
    for currency in supported:
        cur = currency['currency']
        if len(cur) > 3:
            cur = xrpl.utils.hex_to_str(cur)
        issuer = currency['issuer']
        embed.add_field(name=cur, value=f"Issuer: {issuer}\nCode: {currency['currency']}", inline=False)
    await interaction.response.send_message(embed=embed, ephemeral=True)


@tree.command(name='p2p', description='Trade with another user')
async def ptp(interaction: discord.Interaction, user: discord.User, giveamount: float, givecurrency: Literal["XRP", "SOLO", "CSC", "USD", "ZRP"], getamount: float, getcurrency: Literal["XRP", "SOLO", "CSC", "USD", "ZRP"]):
    curMain = givecurrency
    if len(curMain) > 3:
        curMain = helper.str_to_hex(givecurrency)
    userData = helper.getUser(interaction.user.id)
    if userData is None:
        await interaction.response.send_message(
            "You are not registered!", ephemeral=True
        )
        return
    if giveamount <= 0 or getamount <= 0:
        await interaction.response.send_message("Invalid amount", ephemeral=True)
        return
    if givecurrency == getcurrency:
        await interaction.response.send_message("Cannot trade same currency", ephemeral=True)
        return
    if givecurrency != "XRP":
        for tl in userData["tls"]:
            if tl["currency"] == curMain:
                if tl["value"] < giveamount:
                    await interaction.response.send_message("Insufficient balance", ephemeral=True)
                    return
                break
        else:
            await interaction.response.send_message("You don't have a trustline for this currency", ephemeral=True)
            return
    else:
        if userData["xrpBalance"] < giveamount:
            await interaction.response.send_message("Insufficient balance", ephemeral=True)
            return
    userData2 = helper.getUser(user.id)
    if userData2 is None:
        await interaction.response.send_message(
            "The other user is not registered!", ephemeral=True
        )
        return
    if getcurrency != "XRP":
        for tl in userData2["tls"]:
            if tl["currency"] == getcurrency:
                if tl["value"] < getamount:
                    await interaction.response.send_message("The other user has insufficient balance", ephemeral=True)
                    return
                break
        else:
            await interaction.response.send_message("The other user doesn't have a trustline for this currency", ephemeral=True)
            return
    else:
        if userData2["xrpBalance"] < getamount:
            await interaction.response.send_message("The other user has insufficient balance", ephemeral=True)
            return
    embed = discord.Embed(title="Trade Details", color=0x00FF00, description=f"{user.mention} please confirm the trade")
    embed.add_field(name="Give", value=f"{giveamount} {givecurrency}")
    embed.add_field(name="Get", value=f"{getamount} {getcurrency}")
    button = discord.ui.Button(style=discord.ButtonStyle.green, label="Confirm", custom_id="confirm_trade")
    async def callback(interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        #deduct giveamount from user1 and add getamount to user1
        # if givecurrency == "XRP":
        #     #deduct from user1
        #     helper.removeXrpBalance(str(interaction.user.id), giveamount)
        #     #add to user2
        #     helper.addXrpBalance(str(user.id), getamount)
        # if getcurrency == "XRP":
        #     #deduct from user2
        #     helper.removeXrpBalance(str(user.id), getamount)
        #     #add to user1
        #     helper.addXrpBalance(str(interaction.user.id), giveamount)
        # if givecurrency != "XRP":
        #     #deduct from user1
        #     helper.removeTlBalance(str(interaction.user.id), curMain, giveamount)
        #     #add to user2
        #     helper.addTlBalance(str(user.id), curMain, giveamount)
        # if getcurrency != "XRP":
        #     #deduct from user2
        #     helper.removeTlBalance(str(user.id), getcurrency, getamount)
        #     #add to user1
        #     helper.addTlBalance(str(interaction.user.id), getcurrency, getamount)
        embed = discord.Embed(title="Trade Details", color=0x00FF00, description=f"Trade successful")
        embed.add_field(name="Give", value=f"{giveamount} {givecurrency}")
        embed.add_field(name="Get", value=f"{getamount} {getcurrency}")
        embed.add_field(name="From", value=interaction.user.mention)
        embed.add_field(name="To", value=user.mention)
        await interaction.followup.edit_message(embed=embed, view=None, message_id=interaction.message.id)
    button.callback = callback
    view = discord.ui.View()
    view.add_item(button)
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        

# a help command which lists all the commands
@tree.command(name="help", description="List all commands")
async def help(interaction: discord.Interaction):
    embed = discord.Embed(title="Help", color=0x00FF00)
    for command in tree.get_commands():
        embed.add_field(name=command.name, value=command.description, inline=False)
    await interaction.response.send_message(embed=embed, ephemeral=True)

client.run(TOKEN)
