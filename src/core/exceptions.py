"""
Custom Exceptions for I.R.I.S.
Structured error handling across the application
"""


class IRISException(Exception):
    """Base exception for all I.R.I.S. errors"""
    
    def __init__(self, message: str, code: str = "iris_error"):
        self.message = message
        self.code = code
        super().__init__(self.message)
    
    def to_dict(self) -> dict:
        return {
            "error": self.code,
            "message": self.message
        }


class ModelLoadError(IRISException):
    """Failed to load AI model"""
    
    def __init__(self, model_name: str, reason: str = "Unknown error"):
        super().__init__(
            message=f"Failed to load model '{model_name}': {reason}",
            code="model_load_error"
        )
        self.model_name = model_name


class VRAMExhaustedError(IRISException):
    """GPU memory exhausted during generation"""
    
    def __init__(self, required_gb: float = 0, available_gb: float = 0):
        message = "GPU memory exhausted"
        if required_gb and available_gb:
            message = f"GPU memory exhausted: need ~{required_gb:.1f}GB, only {available_gb:.1f}GB available"
        super().__init__(message=message, code="vram_exhausted")
        self.required_gb = required_gb
        self.available_gb = available_gb


class GenerationError(IRISException):
    """Image generation failed"""
    
    def __init__(self, reason: str, seed: int = -1):
        super().__init__(
            message=f"Generation failed: {reason}",
            code="generation_error"
        )
        self.seed = seed


class QueueFullError(IRISException):
    """Generation queue is at capacity"""
    
    def __init__(self, max_size: int):
        super().__init__(
            message=f"Queue is full ({max_size} items). Please wait or clear completed items.",
            code="queue_full"
        )
        self.max_size = max_size


class InvalidParameterError(IRISException):
    """Invalid generation parameter"""
    
    def __init__(self, param: str, value, reason: str = ""):
        message = f"Invalid parameter '{param}': {value}"
        if reason:
            message += f" - {reason}"
        super().__init__(message=message, code="invalid_parameter")
        self.param = param
        self.value = value


class ModelNotLoadedError(IRISException):
    """No model is currently loaded"""
    
    def __init__(self):
        super().__init__(
            message="No model loaded. Please wait for initialization or select a model.",
            code="model_not_loaded"
        )


class ModelDownloadError(IRISException):
    """Failed to download model from HuggingFace Hub"""
    
    def __init__(self, model_name: str, reason: str):
        super().__init__(
            message=f"Failed to download model '{model_name}': {reason}",
            code="model_download_error"
        )
        self.model_name = model_name
        self.reason = reason
    
    def to_dict(self) -> dict:
        return {
            "error": self.code,
            "message": self.message,
            "details": {
                "model_name": self.model_name,
                "reason": self.reason
            }
        }


class AuthenticationError(IRISException):
    """HuggingFace authentication required for gated model"""
    
    def __init__(self, model_name: str):
        super().__init__(
            message=f"Model '{model_name}' requires HuggingFace authentication. Please set HF_TOKEN environment variable.",
            code="authentication_required"
        )
        self.model_name = model_name
    
    def to_dict(self) -> dict:
        return {
            "error": self.code,
            "message": self.message,
            "details": {
                "model_name": self.model_name,
                "instructions": "Visit https://huggingface.co/settings/tokens to create a token"
            }
        }


class DiskSpaceError(IRISException):
    """Insufficient disk space for model download"""
    
    def __init__(self, required_gb: float, available_gb: float):
        super().__init__(
            message=f"Insufficient disk space. Required: {required_gb:.1f}GB, Available: {available_gb:.1f}GB",
            code="insufficient_disk_space"
        )
        self.required_gb = required_gb
        self.available_gb = available_gb
    
    def to_dict(self) -> dict:
        return {
            "error": self.code,
            "message": self.message,
            "details": {
                "required_gb": self.required_gb,
                "available_gb": self.available_gb
            }
        }
