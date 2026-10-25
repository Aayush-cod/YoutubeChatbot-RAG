from typing import List

from langchain_core.documents import Document

from .schemas import Segment


def build_chunks(
    segments: List[Segment], max_chars: int, overlap_chars: int
) -> List[Document]:
    """Group caption segments into ~max_chars chunks, keeping start/end times."""
    # 1) drop blank segments
    segs = [s for s in segments if s.text and s.text.strip()]

    chunks: List[Document] = []
    i = 0  # index of the first segment of the current chunk
    n = len(segs)

    while i < n:
        # 2) add segments until the next one would not fit
        j, size = i, 0
        while j < n and (size == 0 or size + len(segs[j].text) + 1 <= max_chars):
            size += len(segs[j].text) + 1
            j += 1

        group = segs[i:j]
        chunks.append(
            Document(
                page_content=" ".join(s.text.strip() for s in group),
                metadata={
                    "start": int(group[0].start),
                    "end": int(group[-1].start + group[-1].duration),
                },
            )
        )

        if j >= n:  # reached the end of the transcript
            break

        # 3) step back so the next chunk overlaps by about overlap_chars
        back, acc = j, 0
        while back > i + 1 and acc < overlap_chars:
            back -= 1
            acc += len(segs[back].text) + 1

        # 4) always move forward by at least one segment (prevents an infinite loop)
        i = max(back, i + 1)

    return chunks


def fmt_time(seconds: int) -> str:
    """65 -> '1:05', 3725 -> '1:02:05'."""
    seconds = int(seconds)
    hours, rem = divmod(seconds, 3600)
    minutes, secs = divmod(rem, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"