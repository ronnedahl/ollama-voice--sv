#!/bin/bash
# Start Ollama server and pull the model if not already downloaded

ollama serve &
SERVER_PID=$!

# Wait for server to be ready
echo "Waiting for Ollama server..."
until curl -s http://localhost:11434/api/tags > /dev/null 2>&1; do
  sleep 1
done
echo "Ollama server ready"

# Pull model if not present
if ! ollama list | grep -q "llama3.1:8b"; then
  echo "Downloading llama3.1:8b..."
  ollama pull llama3.1:8b
  echo "Model downloaded"
else
  echo "llama3.1:8b already available"
fi

# Keep server running
wait $SERVER_PID
