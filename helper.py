import json
import random
import xrpl
import dotenv
import os
from xrpl.models.requests import AccountInfo, AMMInfo
from xrpl.models.transactions import Payment
from xrpl.models.amounts import IssuedCurrencyAmount
from xrpl.models.currencies import IssuedCurrency, XRP
from xrpl.wallet import Wallet
from xrpl.clients import JsonRpcClient
from xrpl.transaction import autofill_and_sign, submit 
from xrpl.models.response import ResponseStatus
from xrpl.core.keypairs import  derive_keypair
from xrpl.utils import xrp_to_drops

dotenv.load_dotenv()

USERFILE = "users.json"
SUPPORTED = "supported.json" #list of supported currencies
SECRET = os.getenv("SECRET")

def registerUser(dcid):
    try:
        with open(USERFILE, "r") as f:
            users = json.load(f)
    except FileNotFoundError:
        users = {}
    #six digit random number for destination tag
    rNum = random.randint(100000,999999)
    #check all records if the random number is already in use
    while rNum in [users[dcid]["dest"] for dcid in users]:
        rNum = random.randint(100000,999999)
    users[dcid] = {
        "xrpBalance": 0,
        "dest": rNum,
        "tls": []
    }
    with open(USERFILE, "w") as f:
        json.dump(users, f)
    return rNum

def getUser(dcid):
    with open(USERFILE, "r") as f:
        users = json.load(f)
    return users.get(f"{dcid}")

#tl = {"currency": cur, "issuer": iss, "value": val}
def addTl(dcid, tl):
    with open(USERFILE, "r") as f:
        users = json.load(f)
    users[dcid]["tls"].append(tl)
    with open(USERFILE, "w") as f:
        json.dump(users, f)

def addXrpBalance(dcid, amount):
    with open(USERFILE, "r") as f:
        users = json.load(f)
    users[dcid]["xrpBalance"] += amount
    with open(USERFILE, "w") as f:
        json.dump(users, f)

def removeXrpBalance(dcid, amount):
    with open(USERFILE, "r") as f:
        users = json.load(f)
    if users[dcid]["xrpBalance"] < amount:
        return False
    users[dcid]["xrpBalance"] -= amount
    with open(USERFILE, "w") as f:
        json.dump(users, f)
    return True

def getIssuerFromTl(tl):
    with open(SUPPORTED, "r") as f:
        data = json.load(f)
        for i in data:
            if i["currency"] == tl:
                return i["issuer"]
    return None


def addTlBalance(dcid, tl, amount):
    with open(USERFILE, "r") as f:
        users = json.load(f)
    for i in range(len(users[dcid]["tls"])):
        if users[dcid]["tls"][i]["currency"] == tl["currency"]:
            users[dcid]["tls"][i]["value"] += amount
            with open(USERFILE, "w") as f:
                json.dump(users, f)
            return
    else:
        #tl not found
        users[dcid]["tls"].append({"currency": tl["currency"], "issuer": tl["issuer"], "value": amount})
    with open(USERFILE, "w") as f:
        json.dump(users, f)

def removeTlBalance(dcid, tl, amount):
    with open(USERFILE, "r") as f:
        users = json.load(f)
    for i in range(len(users[dcid]["tls"])):
        if users[dcid]["tls"][i]["currency"] == tl["currency"]:
            if users[dcid]["tls"][i]["value"] < amount:
                return False
            users[dcid]["tls"][i]["value"] -= amount
            with open(USERFILE, "w") as f:
                json.dump(users, f)
            return True
    return False

def getSupported():
    with open(SUPPORTED, "r") as f:
        return json.load(f)
    
def getCurData(cur):
    with open(SUPPORTED, "r") as f:
        data = json.load(f)
        for i in data:
            if i["currency"] == cur:
                return i
            
def str_to_hex(s):
    st = xrpl.utils.str_to_hex(s).upper()
    if len(st) < 40:
        st = st+"0"*(40-len(st))
    return st

def sendXRP(senderId, receiverId, amount):
    with open(USERFILE, "r") as f:
        users = json.load(f)
    if users[senderId]["xrpBalance"] < amount:
        return False
    users[senderId]["xrpBalance"] -= amount
    #check if receiver is registered
    if receiverId not in users:
        return False
    users[receiverId]["xrpBalance"] += amount
    with open(USERFILE, "w") as f:
        json.dump(users, f)
    return True

def sendTL(senderId, receiverId, tl, amount):
    with open(USERFILE, "r") as f:
        users = json.load(f)
    for i in range(len(users[senderId]["tls"])):
        if users[senderId]["tls"][i]["currency"] == tl:
            if users[senderId]["tls"][i]["value"] < amount:
                return False
            users[senderId]["tls"][i]["value"] -= amount
            break
    else:
        return False
    for i in range(len(users[receiverId]["tls"])):
        if users[receiverId]["tls"][i]["currency"] == tl:
            users[receiverId]["tls"][i]["value"] += amount
            break
    else:
        users[receiverId]["tls"].append({"currency": tl, "issuer": getIssuerFromTl(tl), "value": amount})
    with open(USERFILE, "w") as f:
        json.dump(users, f)
    return True

def send_xrp_to_wallet(dest, amount, userId, destTag = 1):
    #check if user has enough balance
    if not removeXrpBalance(userId, amount):
        return False
    #check if destination address exists
    try:
        client = JsonRpcClient("https://xrplcluster.com/")
        accReq = AccountInfo(account=dest)
        accRes = client.request(accReq)
        if accRes.status == ResponseStatus.ERROR:
            #refund the user
            addXrpBalance(userId, amount)
            return False
        #initialize wallet
        wallet = Wallet(seed=SECRET, public_key=derive_keypair(SECRET)[0], private_key=derive_keypair(SECRET)[1])
        print(wallet.classic_address)
        #create payment
        payment = Payment(
            account=wallet.classic_address,
            destination=dest,
            amount=xrp_to_drops(amount),
            destination_tag=destTag
        )
        #autofill and sign
        signed_payment = autofill_and_sign(payment, client, wallet)
        #submit
        response = submit(signed_payment, client)
        if response.status == ResponseStatus.SUCCESS:
            return True
        else:
            #refund the user
            addXrpBalance(userId, amount)
            return False
    except Exception as e:
        print(e)
        return False
    
def send_tl_to_wallet(dest, amount, userId, currency, issuer, destTag = 1):
    #check if user has enough balance
    if not removeTlBalance(userId, {"currency": currency, "issuer": issuer}, amount):
        return False
    #check if destination address exists
    try:
        client = JsonRpcClient("https://xrplcluster.com/")
        accReq = AccountInfo(account=dest)
        accRes = client.request(accReq)
        if accRes.status == ResponseStatus.ERROR:
            #refund the user
            addTlBalance(userId, {"currency": currency, "issuer": issuer}, amount)
            return False
        #initialize wallet
        wallet = Wallet(seed=SECRET, public_key=derive_keypair(SECRET)[0], private_key=derive_keypair(SECRET)[1])
        print(wallet.classic_address)
        #create payment
        payment = Payment(
            account=wallet.classic_address,
            destination=dest,
            amount=IssuedCurrencyAmount(
                currency=currency,
                issuer=issuer,
                value=amount
            ),
            destination_tag=destTag
        )
        #autofill and sign
        signed_payment = autofill_and_sign(payment, client, wallet)
        #submit
        response = submit(signed_payment, client)
        if response.status == ResponseStatus.SUCCESS:
            return True
        else:
            #refund the user
            addTlBalance(userId, {"currency": currency, "issuer": issuer}, amount)
            return False
    except Exception as e:
        print(e)
        return False
    
def get_amm_info(client, currency, issuer):
    try:
        ammReq = AMMInfo(asset=XRP(), asset2=IssuedCurrency(currency=currency, issuer=issuer))
        ammRes = client.request(ammReq)
        if ammRes.status == ResponseStatus.SUCCESS:
            return ammRes.result
        else:
            return None
    except Exception as e:
        print(e)
        return None

def get_swap_stats(client, currency, issuer, amount, toXrp):
    ammInfo = get_amm_info(client, currency, issuer)
    if ammInfo is None:
        return None
    if type(ammInfo["amm"]["amount"]) == str:
        token1Supply = float(xrpl.utils.drops_to_xrp(ammInfo["amm"]["amount"]))
    else:
        token1Supply = float(ammInfo["amm"]["amount"]["value"])
    if type(ammInfo["amm"]["amount2"]) == str:
        token2Supply = float(xrpl.utils.drops_to_xrp(ammInfo["amm"]["amount2"]))
    else:
        token2Supply = float(ammInfo["amm"]["amount2"]["value"])
    if toXrp:
        return round(amount * token2Supply / token1Supply, 6)
    else:
        return round(amount * token1Supply / token2Supply, 6)
    
def execute_swap(client, currency, issuer, amount, toXrp, userId):
    print(f"Amount 1: {amount}")
    print(f"Currency: {currency}")
    print(f"Issuer: {issuer}")
    ammInfo = get_amm_info(client, currency, issuer)
    if ammInfo is None:
        return None
    if type(ammInfo["amm"]["amount"]) == str:
        token1Supply = float(xrpl.utils.drops_to_xrp(ammInfo["amm"]["amount"]))
    else:
        token1Supply = float(ammInfo["amm"]["amount"]["value"])
    if type(ammInfo["amm"]["amount2"]) == str:
        token2Supply = float(xrpl.utils.drops_to_xrp(ammInfo["amm"]["amount2"]))
    else:
        token2Supply = float(ammInfo["amm"]["amount2"]["value"])
    print(f"amount 1: {amount}")
    print(f"Token 1 supply: {token1Supply}")
    print(f"Token 2 supply: {token2Supply}")
    if toXrp:
        amount2 = round(amount * token1Supply / token2Supply, 6)
    else:
        amount2 = round(amount * token2Supply / token1Supply, 6)
    print(f"Amount 2: {amount2}")
    slippageAmount = 0.015 * amount2 
    print(f"Slippage amount: {slippageAmount}")
    amountGot = round((amount + token2Supply) / (amount2 + token1Supply), 6)
    #initialize wallet
    wallet = Wallet(seed=SECRET, public_key=derive_keypair(SECRET)[0], private_key=derive_keypair(SECRET)[1])
    if toXrp:
        sendMax = IssuedCurrencyAmount(currency=currency, issuer=issuer, value=round(amount, 6))
        deliverMin = xrp_to_drops(amountGot - slippageAmount)
        payment = Payment(  
            account=wallet.classic_address,
            destination=wallet.classic_address,
            amount="1000000000000000",
            send_max=sendMax,
            deliver_min=deliverMin,
            flags=131072
        )
    else:
        sendMax = xrp_to_drops(amount)
        deliverMin = IssuedCurrencyAmount(currency=currency, issuer=issuer, value=round(amountGot - slippageAmount, 6))
        payment = Payment(
            account=wallet.classic_address,
            destination=wallet.classic_address,
            amount=IssuedCurrencyAmount(currency=currency, issuer=issuer, value="10000000000000"),
            send_max=sendMax,
            deliver_min=deliverMin,
            flags=131072,
        )

    #autofill and sign
    signed_payment = autofill_and_sign(payment, client, wallet)
    #submit
    response = submit(signed_payment, client)
    print(response)
    if response.status == ResponseStatus.SUCCESS:
        #update user balance - deduct the amount and add the amount2
        if toXrp:
            removeTlBalance(userId, {"currency": currency, "issuer": issuer}, amount)
            addXrpBalance(userId, amount2)
        else:
            removeXrpBalance(userId, amount)
            addTlBalance(userId, {"currency": currency, "issuer": issuer}, amount2)
        return True
    else:
        return False
    
if __name__ == '__main__':
    # send_xrp_to_wallet("rbKoFeFtQr2cRMK2jRwhgTa1US9KU6v4L", 1, "739375301578194944")
    print(get_swap_stats("534F4C4F00000000000000000000000000000000","rsoLo2S1kiGeCcn6hCUXVrCpGMWLrRrLZz",10,False))