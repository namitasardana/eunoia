# Eunoia - A Mental Health Bot [for early signs and detection]
Eunoia is designed to help young adults detect early signs of mental discomfort before situations escalate. Instead of waiting days or weeks for appointments, Eunoia provides quick, approachable check-ins to encourage awareness and timely support, also act as a friend who never judges. It is followed by giving motivational quotes to keep going even if the times are hard. It avoids providing hallucinated answers to use queries and suggest them to refer to a practitioner if a situation like this arise.


# Run Instructions

####[optional] Create and activate a virtual environment
conda create -n mental-bot python=3.12 -y
conda activate mental-bot

####Install Dependencies
pip install -r requirements.txt

####In a separate terminal, start Ollama and make sure you have pulled the models first
ollama pull nomic-embed-text
ollama pull mistral:latest

[macos] OLLAMA_HOST=127.0.0.1:11435 ollama serve
[windows] $env:OLLAMA_HOST = "127.0.0.1:11435" ollama serve

####[one-time setup] Build the Vector Indices 
python -m src.build_index

This will generate FAISS indexes + embedding files in the target/ directory.

####Run a search
python -m src.search

####Evaluate and save the results inside the 'target' directory
python -m src.evaluate

####Run the webapp
python app.py