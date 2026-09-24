import pytest
from backend.session import is_sentence_transformer_vectorizer

def test_is_sentence_transformer_vectorizer_names():
    assert is_sentence_transformer_vectorizer("st") is True
    assert is_sentence_transformer_vectorizer("ST") is True
    assert is_sentence_transformer_vectorizer("sentence_transformer") is True
    assert is_sentence_transformer_vectorizer("sentence_transformers") is True
    assert is_sentence_transformer_vectorizer("sentense_transformer") is True
    assert is_sentence_transformer_vectorizer("st:all-MiniLM-L6-v2") is True
    assert is_sentence_transformer_vectorizer("st_default") is True

    # Other vectorizers
    assert is_sentence_transformer_vectorizer("ollama") is False
    assert is_sentence_transformer_vectorizer("openai") is False
    assert is_sentence_transformer_vectorizer("tfidf") is False
    assert is_sentence_transformer_vectorizer(None) is False

def test_is_sentence_transformer_vectorizer_config():
    assert is_sentence_transformer_vectorizer("custom", {"vectorizer_name": "st"}) is True
    assert is_sentence_transformer_vectorizer(None, {"vectorizer": "sentence_transformer"}) is True
    assert is_sentence_transformer_vectorizer("custom", {"vectorizer_name": "ollama"}) is False