from flask import Flask, request
from flask_socketio import SocketIO, emit, disconnect
import random
from collections import defaultdict

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

user_info = {}  # {session_id: {nickname: str, topics: list}}
active_chats = {}  # {session_id: partner_session_id}
waiting_queues = defaultdict(list)  # {topic: [session_ids]}
users_in_queue = set()  # To prevent duplicate joins

nickname_themes = {
    "gaming": {"adjectives": ["Shadow", "Pixel", "Cyber"], "nouns": ["Gamer", "Warrior", "Ninja"]},
    "movies": {"adjectives": ["Cinematic", "Action", "Fantasy"], "nouns": ["Buff", "Critic", "Star"]},
    "music": {"adjectives": ["Melodic", "Electric", "Funky"], "nouns": ["Vibes", "Beat", "Diva"]},
    "tech": {"adjectives": ["Binary", "Quantum", "Cyber"], "nouns": ["Coder", "Bot", "Hacker"]},
    "random": {"adjectives": ["Mystery", "Silent", "Hidden"], "nouns": ["Stranger", "Anon", "Ghost"]}
}

def generate_nickname(topic):
    theme = nickname_themes.get(topic, nickname_themes["random"])
    return f"{random.choice(theme['adjectives'])}{random.choice(theme['nouns'])}{random.randint(1, 999)}"

@app.route("/")
def home():
    return "WebSocket server is running!"

@socketio.on("join")
def handle_join(data):
    user = request.sid
    topics = data.get("topics", ["random"])

    if user in users_in_queue:
        print(f"User {user} tried to join again, ignoring.")
        return  

    users_in_queue.add(user)
    nickname = generate_nickname(topics[0])
    user_info[user] = {"nickname": nickname, "topics": topics}

    emit("nickname", nickname)

    # Add user to all selected topics
    for topic in topics:
        if user not in waiting_queues[topic]:
            waiting_queues[topic].append(user)

    print(f"User {user} ({nickname}) joined topics {topics}.")
    try_match()

def try_match():
    matched_users = set()

    for topic, queue in list(waiting_queues.items()):  
        queue[:] = [u for u in queue if u in user_info]  # Remove disconnected users

        while len(queue) >= 2:
            user1 = queue.pop(0)
            user2 = queue.pop(0)

            if user1 == user2:  
                queue.append(user1)
                continue

            active_chats[user1] = user2
            active_chats[user2] = user1

            emit("matched", {"partner_nickname": user_info[user2]["nickname"]}, room=user1)
            emit("matched", {"partner_nickname": user_info[user1]["nickname"]}, room=user2)

            print(f"Matched {user1} ({user_info[user1]['nickname']}) with {user2} ({user_info[user2]['nickname']}) in topic {topic}.")
            matched_users.update({user1, user2})

    for user in matched_users:
        users_in_queue.discard(user)

@socketio.on("disconnect")
def handle_disconnection():
    user = request.sid
    partner = active_chats.pop(user, None)

    if partner:
        del active_chats[partner]
        emit("partner_left", {"message": "Your chat partner left. Searching for a new match..."}, room=partner)
        if partner in user_info:
            topics = user_info[partner]["topics"]
            for topic in topics:
                if partner not in waiting_queues[topic]:
                    waiting_queues[topic].append(partner)
            try_match()

    if user in user_info:
        topics = user_info[user]["topics"]
        for topic in topics:
            if user in waiting_queues[topic]:
                waiting_queues[topic].remove(user)
    user_info.pop(user, None)
    users_in_queue.discard(user)
@socketio.on("message")
def handle_message(data):
    sender = request.sid
    if sender in active_chats:
        receiver = active_chats[sender]
        message_data = {"text": data["message"], "from": user_info[sender]["nickname"]}

        # Send message to both users
        emit("message", message_data, room=sender)  # Show message in sender's chatbox
        emit("message", message_data, room=receiver)  # Send message to receiver
@socketio.on("message")
def handle_message(data):
    sender = request.sid
    if sender in active_chats:
        receiver = active_chats[sender]
        message_data = {"text": data["message"], "from": user_info[sender]["nickname"]}

        print(f"Message received from {user_info[sender]['nickname']} to {user_info[receiver]['nickname']}: {data['message']}")  # Debugging print

        emit("message", message_data, room=sender)  # Show message in sender's chatbox
        emit("message", message_data, room=receiver)  # Send message to receiver



if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    socketio.run(app, host="0.0.0.0", port=port)
