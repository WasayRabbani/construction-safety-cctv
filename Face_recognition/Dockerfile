# 1. Use the official Miniconda image (contains Python and Conda)
FROM continuumio/miniconda3

# 2. Set up the working directory inside the container
WORKDIR /app

# 3. Install necessary system packages for OpenCV
RUN apt-get update && apt-get install -y \
    libgl1 \
    libglib2.0-0 \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# 4. Install dlib via Conda! 
# (This downloads a pre-compiled binary instead of building from source, skipping the OOM error entirely!)
RUN conda install -y -c conda-forge dlib

# 5. Copy the requirements file into the container and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 6. Copy all the rest of the AI files into the container
COPY . .

# 7. Expose the port that Hugging Face Spaces requires (7860)
EXPOSE 7860

# 8. Start the Master AI Server
CMD ["python", "app.py"]
