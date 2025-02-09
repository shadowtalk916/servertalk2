import asyncio
import websockets
import random
from collections import defaultdict

# Use locks to prevent race conditions with shared data
waiting_users_lock = asyncio.Lock()
active_chats_lock = asyncio.Lock()

waiting_users = set()  # Stores (websocket, nickname) tuples
active_chats = defaultdict(lambda: None)  # Stores bidirectional connections

nickname_themes = {
    "gaming": ["ShadowGamer", "PixelWarrior", "NoobSlayer", "GameOver"],
    "movies": ["CineFan", "MovieBuff", "ActionHero", "OscarWinner"],
    "music": ["RockStar", "DJVibes", "MelodyMaker", "BassBooster"],
    "tech": ["CodeMaster", "AI_Guru", "CyberHacker", "TechWizard"],
    "default": ["Anon1", "MysteryUser", "SecretTalker", "ChatGhost"]
}

def generate_nickname(topic):
    """Sanitize topic input and generate nickname"""
    clean_topic = (topic or "default").strip().lower()
    return random.choice(nickname_themes.get(clean_topic, nickname_themes["default"]))

async def match_users(websocket):
    """Match users with proper error handling"""
    try:
        await websocket.send("Enter a topic (e.g., gaming, movies, tech):")
        topic = await websocket.recv()
        nickname = generate_nickname(topic)
        await websocket.send(f"Your nickname is: {nickname}")

        async with waiting_users_lock:
            waiting_users.add((websocket, nickname))

        while True:
            async with waiting_users_lock:
                if len(waiting_users) >= 2 and (websocket, nickname) in waiting_users:
                    # Remove both users atomically
                    waiting_users.remove((websocket, nickname))
                    partner, partner_nickname = waiting_users.pop()
                    
                    async with active_chats_lock:
                        active_chats[websocket] = partner
                        active_chats[partner] = websocket

                    # Notify both users
                    await asyncio.gather(
                        websocket.send(f"Matched! Chatting with {partner_nickname}"),
                        partner.send(f"Matched! Chatting with {nickname}")
                    )
                    
                    # Start bidirectional chat
                    await asyncio.gather(
                        chat_session(websocket, partner, nickname, partner_nickname),
                        chat_session(partner, websocket, partner_nickname, nickname)
                    )
                    break
            await asyncio.sleep(1)

    except (websockets.exceptions.ConnectionClosed, asyncio.CancelledError):
        await cleanup_connection(websocket)

async def chat_session(sender, receiver, sender_nick, receiver_nick):
    """Handle bidirectional messaging with timeouts"""
    try:
        while True:
            message = await asyncio.wait_for(sender.recv(), timeout=300)
            await receiver.send(f"{sender_nick}: {message}")
            
    except (asyncio.TimeoutError, websockets.exceptions.ConnectionClosed):
        await end_chat(sender, receiver)

async def end_chat(user1, user2):
    """Safely end chat and cleanup"""
    async with active_chats_lock:
        for user in [user1, user2]:
            if active_chats[user]:
                del active_chats[user]

    # Notify users if still connected
    for user in [user1, user2]:
        try:
            await user.send("Partner disconnected. Reconnecting...")
            asyncio.create_task(match_users(user))
        except (websockets.exceptions.ConnectionClosed, RuntimeError):
            pass

async def cleanup_connection(websocket):
    """Handle abandoned connections"""
    async with waiting_users_lock, active_chats_lock:
        # Remove from waiting list
        for entry in list(waiting_users):
            if entry[0] == websocket:
                waiting_users.remove(entry)
        
        # Remove from active chats
        partner = active_chats.get(websocket)
        if partner:
            del active_chats[partner]
            del active_chats[websocket]
            try:
                await partner.send("Partner disconnected. Reconnecting...")
                asyncio.create_task(match_users(partner))
            except websockets.exceptions.ConnectionClosed:
                pass

async def handler(websocket):
    """Connection handler with proper cleanup"""
    try:
        await match_users(websocket)
    finally:
        await cleanup_connection(websocket)

async def main():
    async with websockets.serve(handler, "0.0.0.0", 8080, ping_interval=None):
        print("WebSocket server running on ws://0.0.0.0:8080")
        await asyncio.Future()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nServer shut down gracefully")
