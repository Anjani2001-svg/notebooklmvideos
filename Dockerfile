FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    wget \
    fontconfig \
    fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

# Install Poppins from Google Fonts
RUN mkdir -p /usr/share/fonts/truetype/google-fonts && \
    wget -q "https://github.com/google/fonts/raw/main/ofl/poppins/Poppins-Bold.ttf" \
         -O /usr/share/fonts/truetype/google-fonts/Poppins-Bold.ttf && \
    wget -q "https://github.com/google/fonts/raw/main/ofl/poppins/Poppins-Medium.ttf" \
         -O /usr/share/fonts/truetype/google-fonts/Poppins-Medium.ttf && \
    wget -q "https://github.com/google/fonts/raw/main/ofl/poppins/Poppins-Regular.ttf" \
         -O /usr/share/fonts/truetype/google-fonts/Poppins-Regular.ttf && \
    fc-cache -fv

# Set working directory
WORKDIR /app

# Copy requirements first (layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy app files
COPY . .

# Create temp directory
RUN mkdir -p /tmp/slc_merger

# Expose port
EXPOSE 8501

# Health check
HEALTHCHECK CMD curl --fail http://localhost:8501/_stcore/health || exit 1

# Run
CMD ["streamlit", "run", "app.py", \
     "--server.port=8501", \
     "--server.address=0.0.0.0", \
     "--server.headless=true", \
     "--server.maxUploadSize=500", \
     "--browser.gatherUsageStats=false"]
