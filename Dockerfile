# Gunakan base image Python 3.12.3
FROM python:3.12.3-slim


# Gunakan PyTorch image dengan CUDA 12.6 runtime
#FROM pytorch/pytorch:2.3.1-cuda12.6-cudnn8-runtime
#FROM nvidia/cuda:12.6.0-runtime-ubuntu20.04


# Set working directory di dalam container
WORKDIR /app

# Salin file requirements.txt ke dalam container
COPY requirements.txt .

# Install dependencies dari requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Salin semua file ke dalam container
COPY . .

# Tentukan perintah yang dijalankan saat container dijalankan
CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0", "--server.runOnSave=true"]