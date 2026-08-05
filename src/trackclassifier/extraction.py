from pathlib import Path

from threadpoolctl import threadpool_limits

from .features import FeatureExtractor, TrackAnalysis


def extract_one(
    extractor: FeatureExtractor, path: Path
) -> tuple[TrackAnalysis | None, str | None]:
    with threadpool_limits(limits=1):
        try:
            return extractor.extract(path), None
        except Exception as erro:
            return None, str(erro)
