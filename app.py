from flask import Flask, render_template, request, jsonify
import random
from src.utils import generate_with_ollama_stream  # your bot function

app = Flask(__name__)

# Motivational quotes (shown in header / background cycle)
QUOTES = [
    "Your mental health matters more than your productivity.",
    "Healing takes time, and that’s okay.",
    "You are not alone in this journey.",
    "Small steps every day lead to big changes.",
    "Rest is productive too.",
    "It’s okay to not be okay.",
    "Progress, not perfection.",
    "You are stronger than you think.",
    "Breathe. You are doing enough.",
    "Every day is a new chance to grow.",
    "Self-care is not selfish.",
    "You deserve peace and happiness.",
    "Don’t compare your chapter 1 to someone else’s chapter 20.",
    "You’re allowed to set boundaries.",
    "Take it one step at a time."
]

# ~50 supportive chat add-ons
SUPPORTIVE_MESSAGES = [
    "I’m really glad you’re here today",
    "You don’t have to go through this alone.",
    "It’s okay to take things slow.",
    "I hear you, and I care.",
    "Thanks for sharing your feelings with me.",
    "You deserve kindness, especially from yourself.",
    "You’re safe here — no judgement, just support.",
    "Even small steps count as progress.",
    "I’m here whenever you want to talk.",
    "It’s completely okay to feel the way you do.",
    "Your feelings are valid and important.",
    "I’m happy to listen anytime you need.",
    "You are not a burden for feeling this way.",
    "Taking care of yourself is important.",
    "It’s okay to ask for help when you need it.",
    "Healing isn’t linear, and that’s normal.",
    "You’re stronger than the challenges you face.",
    "Every step forward matters, no matter how small.",
    "I’m proud of you for opening up.",
    "You don’t need to have it all figured out right now.",
    "You’re doing the best you can, and that’s enough.",
    "I believe in you and your ability to get through this.",
    "It’s okay to rest and recharge.",
    "Your worth isn’t measured by productivity.",
    "You bring value just by being yourself.",
    "You deserve to feel safe and supported.",
    "You’re not defined by your struggles.",
    "It’s okay to have bad days.",
    "I appreciate you for being honest about your feelings.",
    "Your courage to share means a lot.",
    "You matter more than you realize.",
    "The fact you’re here shows your strength.",
    "You are not alone, even when it feels that way.",
    "Your story is important and worth telling.",
    "I’m here for you, always.",
    "It’s okay to take breaks when you need them.",
    "Self-care isn’t selfish, it’s necessary.",
    "You deserve gentleness in tough moments.",
    "No emotion is too small or unimportant.",
    "I admire your honesty with yourself.",
    "You’re worthy of love and kindness.",
    "Every day is a new chance to heal.",
    "I’m proud of you for choosing to talk.",
    "It’s normal to feel overwhelmed sometimes.",
    "You are enough, just as you are.",
    "I’ll walk with you through this, step by step.",
    "Your well-being matters deeply.",
    "You’ve already made progress by reaching out.",
    "It’s okay to feel uncertain — it’s part of being human.",
    "Your presence in this world makes it better.",
    "You’re not alone in facing this challenge."
]

# Backgrounds
BACKGROUNDS = [
    "linear-gradient(120deg, #89f7fe, #66a6ff)",
    "linear-gradient(120deg, #f6d365, #fda085)",
    "linear-gradient(120deg, #cfd9df, #e2ebf0)",
    "linear-gradient(120deg, #a1c4fd, #c2e9fb)",
    "linear-gradient(120deg, #d4fc79, #96e6a1)",
    "linear-gradient(120deg, #ffecd2, #fcb69f)",
    "linear-gradient(120deg, #fbc2eb, #a6c1ee)",
    "linear-gradient(120deg, #fad0c4, #ffd1ff)",
    "linear-gradient(120deg, #84fab0, #8fd3f4)",
    "linear-gradient(120deg, #e0c3fc, #8ec5fc)",
    "linear-gradient(120deg, #ff9a9e, #fecfef)",
    "linear-gradient(120deg, #43e97b, #38f9d7)",
    "linear-gradient(120deg, #30cfd0, #330867)",
    "linear-gradient(120deg, #667eea, #764ba2)",
    "linear-gradient(120deg, #fddb92, #d1fdff)"
]

@app.route("/")
def home():
    quote = random.choice(QUOTES)
    bg = random.choice(BACKGROUNDS)
    return render_template(
        "index.html",
        quote=quote,
        background=bg,
        quotes=QUOTES,
        backgrounds=BACKGROUNDS
    )

@app.route("/ask", methods=["POST"])
def ask():
    data = request.get_json()
    user_input = data.get("question", "").strip()

    if not user_input:
        return jsonify({"answer": "Please enter a question."})

    # Call your Ollama bot
    bot_answer = "".join(generate_with_ollama_stream(user_input))

    # Add supportive message
    supportive = random.choice(SUPPORTIVE_MESSAGES)

    # Wrap supportive text in <span> for styling
    final_answer = f"{bot_answer}<br><span class='supportive-msg'> {supportive}</span>"

    return jsonify({"answer": final_answer})

if __name__ == "__main__":
    app.run(debug=True)
