import asyncio
import websockets
import random

waiting_users = set()  # Users waiting for a chat
active_chats = {}  # Stores active chat pairs

# Nickname themes based on topics
nickname_themes = {
    "gaming": ["ShadowGamer", "PixelWarrior", "NoobSlayer", "GameOver"],
    "movies": ["CineFan", "MovieBuff", "ActionHero", "OscarWinner"],
    "music": ["RockStar", "DJVibes", "MelodyMaker", "BassBooster"],
    "tech": ["CodeMaster", "AI_Guru", "CyberHacker", "TechWizard"],
    "default": ["Anon1", "MysteryUser", "SecretTalker", "ChatGhost"]
}

def generate_nickname(topic):
    """Returns a random nickname based on the chosen topic."""
    return random.choice(nickname_themes.get(topic.lower(), nickname_themes["default"]))

async def match_users(websocket):
    """Matches users into chat pairs."""
    await websocket.send("Enter a topic (e.g., gaming, movies, tech):")
    topic = await websocket.recv()
    nickname = generate_nickname(topic)
    await websocket.send(f"Your nickname is: {nickname}")

    waiting_users.add((websocket, nickname))

    while (websocket, nickname) in waiting_users:
        if len(waiting_users) >= 2:
            waiting_users.remove((websocket, nickname))
            partner, partner_nickname = waiting_users.pop()
            active_chats[websocket] = partner
            active_chats[partner] = websocket

            await websocket.send(f"Matched! You're chatting with {partner_nickname}. Start chatting!")
            await partner.send(f"Matched! You're chatting with {nickname}. Start chatting!")

            await chat_session(websocket, partner, nickname, partner_nickname)
            break
        await asyncio.sleep(1)

async def chat_session(user1, user2, nickname1, nickname2):
    """Handles messaging between two users."""
    try:
        while True:
            message1 = await user1.recv()
            await user2.send(f"{nickname1}: {message1}")

            message2 = await user2.recv()
            await user1.send(f"{nickname2}: {message2}")

    except websockets.exceptions.ConnectionClosed:
        await end_chat(user1, user2)

async def end_chat(user1, user2):
    """Ends the chat and requeues users if needed."""
    if user1 in active_chats:
        del active_chats[user1]
    if user2 in active_chats:
        del active_chats[user2]

    await user1.send("Partner left. Searching for a new match...")
    await user2.send("Partner left. Searching for a new match...")

    asyncio.create_task(match_users(user1))
    asyncio.create_task(match_users(user2))

async def handler(websocket):
    """Handles incoming WebSocket connections."""
    await match_users(websocket)

async def main():
    async with websockets.serve(handler, "0.0.0.0", 8080):  # Change port if needed
        await asyncio.Future()

print("WebSocket server is running on ws://0.0.0.0:8080")
asyncio.run(main())
