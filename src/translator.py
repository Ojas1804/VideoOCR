import torch
from transformers import MarianMTModel, MarianTokenizer

_MODEL_NAME = "Helsinki-NLP/opus-mt-ja-en"

_tokenizer: MarianTokenizer | None = None
_model: MarianMTModel | None = None
_device: torch.device | None = None

def _load_model() -> None:
    """Load the MarianMT model and tokeniser on first call (lazy singleton)."""
    global _tokenizer, _model, _device
    if _model is not None:
        return  # already loaded

    print(f"[translator] Loading '{_MODEL_NAME}' …")
    _tokenizer = MarianTokenizer.from_pretrained(_MODEL_NAME)
    _model = MarianMTModel.from_pretrained(_MODEL_NAME)
    _model.eval()

    _device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    _model.to(_device)

    device_label = f"GPU ({torch.cuda.get_device_name(0)})" if _device.type == "cuda" else "CPU"
    print(f"[translator] Model ready on {device_label}.")

def translate_texts(texts: list[str], batch_size: int = 16, on_item=None) -> dict[str, str]:
    """
    Translate a list of Japanese strings to English.

    Args:
        texts:      Source strings (duplicates are collapsed).
        batch_size: Inference batch size.
        on_item:    Optional callback(src: str, tgt: str) called after each
                    string is translated — used by the web server to stream
                    per-translation progress events.
    """
    _load_model()
    unique_texts = list(dict.fromkeys(t for t in texts if t.strip()))
    if not unique_texts:
        return {}
    translations: dict[str, str] = {}
    for i in range(0, len(unique_texts), batch_size):
        batch = unique_texts[i : i + batch_size]
        inputs = _tokenizer(
            batch,
            return_tensors="pt",
            padding=True,
            truncation=True,
            max_length=128,
        )
        inputs = {k: v.to(_device) for k, v in inputs.items()}
        with torch.no_grad():
            translated_ids = _model.generate(**inputs)
        decoded = _tokenizer.batch_decode(translated_ids, skip_special_tokens=True)
        for src, tgt in zip(batch, decoded):
            translations[src] = tgt
            if on_item:
                on_item(src, tgt)
    return translations