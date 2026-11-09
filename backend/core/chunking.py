"""Split extracted text into overlapping passages ("chunks") for search.

Pure Python, no Django. Chunks break at paragraph and sentence boundaries where
possible. Sizes are in characters: 1200 characters is roughly 300 English tokens,
or up to about 480 Hindi/Gujarati tokens, which fits the 512-token limit of the
embedding model.
"""
import re

# sentence ends: . ! ? and the Hindi/Gujarati danda marks
_SENTENCE_END = re.compile(r"(?<=[.!?\u0964\u0965])\s+")


def _units(text, size):
    """Break text into small pieces: (piece, starts_on_new_line)."""
    pieces = []
    for line in text.split("\n"):
        line = line.strip()
        if not line:
            continue
        first = True
        for sentence in _SENTENCE_END.split(line):
            sentence = sentence.strip()
            while len(sentence) > size:  # one huge unbroken run: cut it at a space
                cut = sentence.rfind(" ", 0, size)
                if cut < size // 2:
                    cut = size
                pieces.append((sentence[:cut].strip(), first))
                first = False
                sentence = sentence[cut:].strip()
            if sentence:
                pieces.append((sentence, first))
                first = False
    return pieces


def _join(units):
    out = ""
    for index, (piece, new_line) in enumerate(units):
        out = piece if index == 0 else out + ("\n" if new_line else " ") + piece
    return out


def split_text(text, size=1200, overlap=200):
    """Return a list of chunk strings of at most about `size` characters."""
    units = _units(text, size)
    chunks, current, length = [], [], 0

    for unit in units:
        add = len(unit[0]) + 1
        if current and length + add > size:
            chunks.append(_join(current))
            tail, tail_length = [], 0
            for previous in reversed(current):  # carry the last few units over as overlap
                if tail_length + len(previous[0]) + 1 > overlap:
                    break
                tail.insert(0, previous)
                tail_length += len(previous[0]) + 1
            if tail_length + add > size:
                tail, tail_length = [], 0
            current, length = tail, tail_length
        current.append(unit)
        length += add

    if current:
        chunks.append(_join(current))
    return chunks