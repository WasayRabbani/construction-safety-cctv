import torch
import sys

print("-" * 50)
print(f"Python Version: {sys.version}")
print(f"PyTorch Version: {torch.__version__}")
print("-" * 50)

print(f"Is CUDA (GPU) available? : {torch.cuda.is_available()}")

if torch.cuda.is_available():
    print(f"GPU Name: {torch.cuda.get_device_name(0)}")
    print(f"CUDA Version: {torch.version.cuda}")
    print(f"Number of GPUs: {torch.cuda.device_count()}")
    print("\n✅ YOUR GPU IS READY! If the main script still says 'No GPU', we just need to restart the environment.")
else:
    print("\n❌ GPU NOT DETECTED BY PYTORCH.")
    print("\nPossible solutions:")
    print("1. Run: pip uninstall torch torchvision torchaudio -y")
    print("2. Run: pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118")
    print("   (Note: Try cu121 if cu118 doesn't work)")
print("-" * 50)