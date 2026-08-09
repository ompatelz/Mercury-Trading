import hashlib
import math
import re

EMBEDDING_DIMENSIONS = 32
TOKEN_PATTERN = re.compile(r"[a-z0-9_]+")


def embed_text(text: str) -> list[float]:
    vector = [0.0] * EMBEDDING_DIMENSIONS
    for token in TOKEN_PATTERN.findall(text.lower()):
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        bucket = digest[0] % EMBEDDING_DIMENSIONS
        sign = 1.0 if digest[1] % 2 == 0 else -1.0
        vector[bucket] += sign
    length = math.sqrt(sum(value * value for value in vector))
    if length == 0:
        return vector
    return [value / length for value in vector]


def cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    return sum(left[index] * right[index] for index in range(len(left)))
