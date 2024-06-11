#an incoming transaction stream listener for the XRP ledger
import asyncio
from threading import Thread
import xrpl
import xrpl.asyncio
import json

USER_FILE = "users.json"
DESTADDR = "rJAFQ2d6mUTgHHtLogPx5BB5NRT97ASFDy"

class XRPLMonitorThread(Thread):
    def __init__(self, url):
        Thread.__init__(self, daemon=True)
        self.url = url
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.loop.set_debug(True)

    def add_xrp_balance(self, amount, destTag):
        with open(USER_FILE, "r") as f:
            users = json.load(f)
        #check which user has the destination tag
        for user in users:
            if int(users[user]["dest"]) == int(destTag):
                users[user]["xrpBalance"] += round(amount, 6)
                with open(USER_FILE, "w") as f:
                    json.dump(users, f)
                return
            
    def add_tl_balance(self, amount, destTag, currency, issuer):
        with open(USER_FILE, "r") as f:
            users = json.load(f)
        #check which user has the destination tag
        for user in users:
            if int(users[user]["dest"]) == int(destTag):
                for tl in users[user]["tls"]:
                    if tl["currency"] == currency and tl["issuer"] == issuer:
                        tl["value"] += amount
                        with open(USER_FILE, "w") as f:
                            json.dump(users, f)
                        return
                users[user]["tls"].append({"currency": currency, "issuer": issuer, "value": amount})
                with open(USER_FILE, "w") as f:
                    json.dump(users, f)
                return

    def run(self):
        self.loop.run_forever()

    async def watch_xrpl(self):
        async with xrpl.asyncio.clients.AsyncWebsocketClient(self.url) as self.client:
            await self.on_connected()
            async for message in self.client:
                mtype = message.get("type")
                engine_result = message.get("engine_result")
                if mtype == "transaction" and (engine_result == "tesSUCCESS" or engine_result == "terQUEUED"):
                    await self.on_transaction(message)

    async def on_connected(self):
        await self.client.request(xrpl.models.requests.Subscribe(
            accounts=[DESTADDR]
        ))
        print("Connected to XRPL")

    async def on_transaction(self, message):
        print("Transaction received:", message)
        txn = message.get("transaction")
        if txn.get("TransactionType") != "Payment":
            print("Not a payment")
            return
        if txn.get("Destination") != DESTADDR:
            print("Not for me")
            return
        destTag = txn.get("DestinationTag", None)
        if destTag is None:
            print("No destination tag")
            return
        amount = txn.get("Amount")
        if type(amount) == str:
            amount = float(xrpl.utils.drops_to_xrp(amount))
            if amount <= 1 and type(amount) == str:
                return
            print(f"Payment of {amount} XRP received with destination tag {destTag}")
            self.add_xrp_balance(amount, destTag)
        elif type(amount) == dict:
            amountt = float(amount["value"])
            print(f"Payment of {amountt} {amount['currency']} received with destination tag {destTag}")
            self.add_tl_balance(amountt, destTag, amount["currency"], amount["issuer"])


async def main():
    url = "wss://xrpl.ws"
    monitor = XRPLMonitorThread(url)
    monitor.start()
    await monitor.loop.run_until_complete(await monitor.watch_xrpl())

if __name__ == "__main__":
    asyncio.run(main())
