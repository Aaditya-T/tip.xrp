import json
import random
import xrpl

USERFILE = "users.json"
SUPPORTED = "supported.json" #list of supported currencies

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
    
def addTlBalance(dcid, tl, amount):
    with open(USERFILE, "r") as f:
        users = json.load(f)
    for i in range(len(users[dcid]["tls"])):
        if users[dcid]["tls"][i] == tl:
            users[dcid]["tls"][i]["value"] += amount
            with open(USERFILE, "w") as f:
                json.dump(users, f)
            return
    users[dcid]["tls"].append(tl)
    with open(USERFILE, "w") as f:
        json.dump(users, f)

def removeTlBalance(dcid, tl, amount):
    with open(USERFILE, "r") as f:
        users = json.load(f)
    for i in range(len(users[dcid]["tls"])):
        if users[dcid]["tls"][i] == tl:
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

if __name__ == '__main__':
    str_to_hex("SOLO")