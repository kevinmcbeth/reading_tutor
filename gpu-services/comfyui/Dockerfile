FROM nvidia/cuda:12.1.0-runtime-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 python3-pip python3-venv git wget \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /opt/comfyui

# Install ComfyUI
RUN git clone https://github.com/comfyanonymous/ComfyUI.git . && \
    pip3 install --no-cache-dir torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121 && \
    pip3 install --no-cache-dir -r requirements.txt

# Models are loaded from EFS mount at /models
# The checkpoint (DreamShaperXL_Turbo_v2_1.safetensors) should be in /models/checkpoints/
RUN mkdir -p /models/checkpoints

# Configure ComfyUI to use external model directory
ENV COMFYUI_MODEL_PATH=/models

EXPOSE 8188

CMD ["python3", "main.py", "--listen", "0.0.0.0", "--port", "8188", "--extra-model-paths-config", "/models/extra_model_paths.yaml"]
