import discord
import datetime
import time
import json
from discord.ext import commands

# + milestones
# + autosave
# + find errors
# + stripping text from messages

with open("token.txt") as f:
    TOKEN = f.readline()

bot = commands.Bot(command_prefix=".")
bot.remove_command("help")

save_file = "./data.json"
string_file = "./strings.json"
presence = discord.Game(name="with numbers | .help")

count_guilds = {}
PREV_SAVE = time.time()
SAVE_DEL = 10

def reload_strings():
    global MSGS
    global NAMES
    global ERRORS
    with open(string_file) as f:
        data = json.load(f)
    MSGS = data["messages"]
    NAMES = data["names"]
    ERRORS = data["errors"]
    for k in MSGS:
        MSGS[k] = "".join(MSGS[k])

reload_strings()

class Parse:
    def roman(x):
        """Original by @Kantoros1#4862, modified"""
        inp = x
        numerals = {"I":1, "V":5, "X":10, "L":50, "C":100, "D":500, "M":1000}
        
        num = list(inp.upper().replace('__','_'))
        Thousands = False

        for i in range(len(num)):
            if num[i] in numerals:
                num[i] = numerals[num[i]]
            elif num[i] != "_":
                return False
            if num[i] == '_':
                Thousands = not Thousands
            elif Thousands:
                num[i] *= 1000
        
        num = list(filter(lambda a:a != '_',num))
        
        result = 0
        while len(num)>0:
            if num[0] < max(num):
                result -= num[0]
            else:
                result += num[0]
            num.pop(0)
        return result

    def int(x):
        try:
            return int(x)
        except Exception:
            return False

    def bin(x):
        #if False in [i in ["0","1"]for i in x]:#find non 0/1 characters in the string
        #    return False
        #return int(x, 2)
        try:
            return int(x, 2)
        except Exception:
            return False

class Ctypes:
    def inc(old, new):
        return new == old+1
    
    def dec(old, new):
        return new == old-1
    
    def sqr(old, new):
        s = math.sqrt(new)
        return s == int(math.sqrt(old)) + 1

def cutoff(content, chars="0123456789 "):# cut off message after number ends
    out = ""
    for c in content:
        if c not in chars:
            break
        out += c if c != " " else ""
    return out

## p n r b s

CHECKS = {"p":Ctypes.inc, "n":Ctypes.dec, "r":Ctypes.inc,
          "b":Ctypes.inc, "s":Ctypes.sqr}

PARSERS = {"p":Parse.int, "n":Parse.int, "r":Parse.roman,
         "b":Parse.bin, "s":Parse.int}

#move to json?
CHARS = {"p":"0123456789 ", "n":"-0123456789 ", "r":"IVXLCDM_ ",
         "b":"01 ", "s":"0123456789 "}

class Cchannel:
    def __init__(self, channel, ctype):
        """(Channel object, "p")"""
        self.channel = channel
        self.name = channel.name
        self.ctype = ctype
        self.progress = 0
        self.prev = "@someone"

        self.check = CHECKS[ctype]
        self.parse = PARSERS[ctype]

    def try_count(self, txt):
        num = self.parse(cutoff(txt, CHARS[self.ctype]))
        c = self.check(self.progress, num)
        if c:
            self.progress = num
            return True
        return False

    def save(self):
        data = {"progress":self.progress,
                "prev":self.prev}
        return data


def milestr(info):
    value, t, user, prev = info
    date = datetime.date.today()
    # move to json?
    datestr = f"{date.day}/{date.month} - {date.year}"
    return f"`Milestone reached: {value} in #{NAMES[t]} by:` {user}`, with help from` {prev} `on {datestr}`"

class CountGuild:
    def __init__(self, guild):
        self.guild = guild
        self.bot_channel = None
        self.milestone_channel = None
        
        self.channels = {t:None for t in PARSERS}
        
        for channel in guild.channels:
            if channel.name == "bot":
                self.bot_channel = channel
            elif channel.name == "milestones":
                self.milestone_channel = channel
            else:
                for t in self.channels:
                    if NAMES[t] == channel.name:
                        self.channels[t] = Cchannel(channel, t)
        
        if self.bot_channel == None:
            print(f"<{guild.name}> Couldn't find channel 'bot'.")
        if self.milestone_channel == None:
            print(f"<{guild.name}> Couldn't find channel 'milestones'.")
        for channel in self.channels:
            if self.channels[channel] == None:
                print(f"<{guild.name}> Couldn't find channel '{NAMES[channel]}'")

    def load(self, data):
        for c in self.channels:
            if self.channels[c]:
                self.channels[c].progress = data[c]["progress"]
                self.channels[c].prev = data[c]["prev"]

    def save_str(self):
        data = {}
        for c in self.channels:
            if self.channels[c]:
                data[c] = self.channels[c].save()
            else:
                data[c] = None
        return data

    def try_count(self, message):
        """Should only be called if in an actual count channel"""
        #returns True if message should stay
        ctype = ""
        for c in self.channels:
            if self.channels[c].channel.id == message.channel.id:
                ctype = c
                break
        if not ctype:# not a count channel, shouldn't actually happen
            return True# don't want to delete if not in a count channel

        cch = self.channels[ctype]
        
        if message.author.mention == cch.prev:
            return False
        counted = cch.try_count(message.content)

        if counted:
            old = cch.prev
            cch.prev = message.author.mention
            if cch.progress % 1000 == 0:
                return (True, cch.progress, ctype, cch.prev, old)
            
            return True
        return False

#    def ms_update(self, t, user):
#        if self.counts[t] % 1000 != 0:
#            return False
#        self.milestones[t].append(self.counts[t])
#        return milestr(self.counts[t], t, user, self.latest[t])

async def is_master(user):
    own = await bot.is_owner(user)
    if own:
        return True
    for role in user.roles:
        if role.name.lower() == "count master":
            return True
    return False

def load():
    with open(save_file) as f:
        alldata = json.load(f)
    for gldid in alldata:
        data = alldata[gldid]
        
        for gld in count_guilds:
            if str(gld.id) == gldid:
                count_guilds[gld].load(data)
                break
        else:
            print(f"Unused guild: {gldid} in save file")
    print("Loaded counting data")
    
def save():
    data = {}
    for gld in count_guilds:
        data[gld.id] = count_guilds[gld].save_str()
    
    with open(save_file, "w") as fp:
        json.dump(data, fp)

    PREV_SAVE = time.ctime()

@bot.event
async def on_message(message):
    if message.author == bot.user or type(message.channel) == discord.DMChannel:
        return
    gld = count_guilds[message.channel.guild]
    
    if message.channel in [i.channel if i else None for i in gld.channels.values()]:
        counted = gld.try_count(message)
        if not counted:
            await message.delete()
            return
        if type(counted) == tuple:
            await gld.milestone_channel.send(milestr(counted[1:]))
        if time.time() - PREV_SAVE >= SAVE_DEL:
            save()
        
    if message.channel == gld.bot_channel:
        await bot.process_commands(message)

@bot.command(name="find")
async def find_mistakes(ctx, t="p", limit=None):
    gld = count_guilds[ctx.guild]
    
    if not await is_master(ctx.author):
        await ctx.send(ERRORS["perm"])
        return
    
    if t not in gld.channels or gld.channels[t] == None:
        await gld.bot_channel.send(ERRORS["type"])
        return
    
    await ctx.send(f"`Scanning for errors in #{NAMES[t]}`")
    #TODO remember a safe point to not look through all messages
    #TODO ignore messages with a certain reaction OR allow for whitelisting messages
    lim = Parse.int(limit)
    lim = lim if lim else None# False -> None
    history = await gld.channels[t].channel.history(limit=lim).flatten()
    history.reverse()
    
    new = history[0].content
    old = PARSERS[t](cutoff(new, CHARS[t]))

    for msg in history[1:]:
        new = PARSERS[t](cutoff(msg.content, CHARS[t]))
        if not CHECKS[t](old, new):
            await ctx.send(f"`Located miscount or invalid number around {old} - {new}`")
        if new:
            old = new
    await ctx.send("`Done checking for errors.`")

@bot.command(name="set")
async def setcount(ctx, t="p", amount="42"):
    gld = count_guilds[ctx.guild]
    if t not in gld.channels:
        await gld.bot_channel.send(ERRORS["type"])
        return
    if not await is_master(ctx.author):
        await ctx.send(ERRORS["perm"])
        return
    
    n = Parse.int(amount)
    
    if not n:
        await ctx.send(ERRORS["num"])
        return
    gld.channels[t].progress = n
    save()
    await ctx.send(f"`#{NAMES[t]} progress is now {n}`")

@bot.command(name="count")
async def getcount(ctx, t="c"):
    gld = count_guilds[ctx.guild]
    if t not in gld.channels or gld.channels[t] == None:
        await gld.bot_channel.send(ERRORS["type"])
        return
    await gld.bot_channel.send(f"`#{NAMES[t]} progress is {gld.channels[t].progress}`")

@bot.command(name="help")
async def h(ctx):
    await ctx.send(MSGS["help"])

@bot.command(name="credits")
async def cred(ctx):
    await ctx.send(MSGS["credits"])

@bot.command(name="alephnull")
async def kill_bot(ctx):
    if await is_master(ctx.author):
        print(f"Closed by {ctx.author.name}#{ctx.author.discriminator} in guild: {ctx.guild.name}")
        for guild in bot.guilds:
            gld = count_guilds[guild]
            if gld.bot_channel != None:
                await gld.bot_channel.send(MSGS["shutdown"])
        await bot.close()
    else:
        print(f"{ctx.author.mention} tried to kill bot")
        await ctx.send(ERRORS["perm"])

@bot.command(name="save")
async def manual_save(ctx):
    gld = count_guilds[ctx.guild]
    if not await is_master(ctx.author):
        await ctx.send(ERRORS["perm"])
        return
    save()
    await ctx.send("`Saved all counting data`")

def join_msg(gld):
    join = MSGS["join"]
    for ctype in gld.channels:
        if gld.channels[ctype]:
            join += MSGS["progress"].replace("CHANNEL",NAMES[ctype])%gld.channels[ctype].progress
    join += MSGS["join_end"]
    return join

@bot.event
async def on_ready():
    print(f"CONNECTED\n{time.ctime()}\nLogged in as {bot.user.name}")
    await bot.change_presence(activity=presence)

    print("Guilds:")
    for guild in bot.guilds:
        print(guild.name)
        count_guilds[guild] = CountGuild(guild)
    print("-----")
    load()
    for guild in count_guilds:
        gld = count_guilds[guild]
        if gld.bot_channel != None:#alert that the bot has joined
            await gld.bot_channel.send(join_msg(gld))
            
            for c in gld.channels:
                if gld.channels[c] == None:
                    await gld.bot_channel.send(MSGS["channel_error"] % NAMES[c])

@bot.event
async def on_disconnect():
    print(f"Disconnected on {time.ctime()}")
    save()

print("Starting bot")
bot.run(TOKEN)
