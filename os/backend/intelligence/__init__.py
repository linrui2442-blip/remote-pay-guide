__all__ = ["analyze_video"]


def __getattr__(name):
    """Avoid eager database and AI initialization when importing submodules."""
    if name == "analyze_video":
        from .manager import analyze_video

        return analyze_video
    raise AttributeError(name)
