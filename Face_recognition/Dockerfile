# 1. Use the official lightweight Python image from Docker Hub
FROM python:3.10-slim

# 2. Set up the working directory inside the container
WORKDIR /app

# 3. Install necessary system packages for OpenCV (libgl1, libglib2.0)
RUN apt-get update && apt-get install -y \
    libgl1-mesa-glx \
    libglib2.0-0 \
    ffmpeg \
    cmake \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# 4. Copy the requirements file into the container and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 5. Copy all the rest of the AI files into the container
COPY . .

# 6. Expose the port that Hugging Face Spaces requires (7860)
EXPOSE 7860

# 7. Start the Master AI Server
CMD ["python", "app.py"]
